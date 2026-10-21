// Host side of the PDF reader: HTTP routes under /pdf2zh on dsh's web server.
//
//   GET  /pdf2zh/pdfjs/<file>                 pdf.js, served from this plugin's dependency
//   GET  /pdf2zh/config                       default languages, service, kernel
//   POST /pdf2zh/documents                    body: PDF bytes -> { id }
//   POST /pdf2zh/documents/<id>/pages/<n>     -> one translated page as application/pdf
//
// Page requests are queued. While pdf2zh translates, requests for other pages
// of the same document pile up and the next run translates them together
// (pages "3,4,5" in one request to the resident pdf2zh worker).
// Results are cached per document hash, page and translation options.

import { createHash } from 'node:crypto'
import { createReadStream } from 'node:fs'
import { mkdir, mkdtemp, readFile, rm, stat, writeFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { tmpdir } from 'node:os'
import { dirname, extname, join, normalize, sep } from 'node:path'
import { PDFDocument } from 'pdf-lib'
import { translateParams } from './pdf2zh.js'

const require = createRequire(import.meta.url)
const PREFIX = '/pdf2zh'
const ID = /^[a-f0-9]{64}$/
const TYPES = {
  '.mjs': 'text/javascript', '.js': 'text/javascript', '.map': 'application/json',
  '.wasm': 'application/wasm', '.bcmap': 'application/octet-stream', '.pfb': 'application/octet-stream',
  '.ttf': 'font/ttf', '.json': 'application/json',
}

/** Cache key for one page's translation options. */
export function optionsKey(options) {
  return createHash('sha256')
    .update(JSON.stringify([options.langIn, options.langOut, options.service, options.kernel]))
    .digest('hex').slice(0, 16)
}

/**
 * Pending page translations, run one pdf2zh process at a time. Each run takes
 * the oldest request plus queued requests for the same document and options,
 * up to `batch` pages.
 */
export class PageQueue {
  constructor(translate, { batch = 4 } = {}) {
    this.translate = translate // (docId, options, pages[]) => Promise<Map<page, Uint8Array>>
    this.batch = batch
    this.pending = [] // { docId, options, key, page, waiters: Set }
    this.running = false
  }

  /** Resolve with the page's PDF bytes; `signal` withdraws a request that has not started. */
  request(docId, options, page, signal) {
    const key = optionsKey(options)
    let job = this.pending.find(j => j.docId === docId && j.key === key && j.page === page)
    if (!job) {
      job = { docId, options, key, page, waiters: new Set() }
      this.pending.push(job)
    }
    return new Promise((resolve, reject) => {
      const waiter = { resolve, reject }
      job.waiters.add(waiter)
      signal?.addEventListener('abort', () => {
        job.waiters.delete(waiter)
        if (job.waiters.size === 0 && this.pending.includes(job)) {
          this.pending.splice(this.pending.indexOf(job), 1)
        }
        reject(signal.reason ?? new Error('aborted'))
      }, { once: true })
      queueMicrotask(() => this.pump())
    })
  }

  async pump() {
    if (this.running || this.pending.length === 0) return
    this.running = true
    const first = this.pending[0]
    const jobs = this.pending
      .filter(j => j.docId === first.docId && j.key === first.key)
      .slice(0, this.batch)
    this.pending = this.pending.filter(j => !jobs.includes(j))
    try {
      const pages = await this.translate(first.docId, first.options, jobs.map(j => j.page).sort((a, b) => a - b))
      for (const job of jobs) {
        const bytes = pages.get(job.page)
        for (const w of job.waiters) bytes ? w.resolve(bytes) : w.reject(new Error(`page ${job.page} missing`))
      }
    } catch (error) {
      for (const job of jobs) for (const w of job.waiters) w.reject(error)
    } finally {
      this.running = false
      this.pump()
    }
  }
}

/** Copy the given 1-based pages out of a PDF into one single-page PDF each. */
export async function splitPages(bytes, pages) {
  const source = await PDFDocument.load(bytes)
  const out = new Map()
  for (const page of pages) {
    if (page < 1 || page > source.getPageCount()) continue
    const single = await PDFDocument.create()
    const [copied] = await single.copyPages(source, [page - 1])
    single.addPage(copied)
    out.set(page, await single.save())
  }
  return out
}

/** Create the reader's route handler; `translate(params)` runs one worker request. */
export function createViewer(config, { cacheDir = join(tmpdir(), 'dsh-pdf2zh'), translate }) {
  const docs = join(cacheDir, 'documents')
  const pageDir = (id, key) => join(cacheDir, 'pages', id, key)
  const pdfjsRoot = dirname(require.resolve('pdfjs-dist/package.json'))

  const queue = new PageQueue(async (id, options, pages) => {
    const work = await mkdtemp(join(cacheDir, 'run-'))
    try {
      const result = await translate(translateParams(join(docs, `${id}.pdf`), work, { ...options, pages: pages.join(',') }))
      const mono = result.results?.[0]?.mono
      if (!mono) throw new Error('pdf2zh returned no translated PDF')
      const split = await splitPages(await readFile(mono), pages)
      const dir = pageDir(id, optionsKey(options))
      await mkdir(dir, { recursive: true })
      await Promise.all([...split].map(([page, bytes]) => writeFile(join(dir, `${page}.pdf`), bytes)))
      return split
    } finally {
      await rm(work, { recursive: true, force: true })
    }
  }, { batch: config.viewerBatch })

  async function translatePage(id, page, options, signal) {
    const cached = join(pageDir(id, optionsKey(options)), `${page}.pdf`)
    try {
      return await readFile(cached)
    } catch {
      return await queue.request(id, options, page, signal)
    }
  }

  return async function handle(req, res) {
    const url = new URL(req.url, 'http://local')
    const path = url.pathname.slice(PREFIX.length)
    try {
      if (req.method === 'GET' && path.startsWith('/pdfjs/')) {
        return await serveStatic(res, pdfjsRoot, decodeURIComponent(path.slice('/pdfjs/'.length)))
      }
      if (req.method === 'GET' && path === '/config') {
        return sendJson(res, 200, {
          langIn: config.langIn, langOut: config.langOut, service: config.service, kernel: config.kernel,
        })
      }
      if (req.method !== 'POST') return sendJson(res, 405, { error: 'method not allowed' })
      // Plugin routes get no dsh authentication: refuse anything a page on
      // another origin could send. A custom header forces a CORS preflight,
      // which this route never approves.
      if (req.headers['x-pdf2zh'] !== '1' || !sameOrigin(req)) {
        return sendJson(res, 403, { error: 'forbidden' })
      }
      if (path === '/documents') {
        const bytes = await readBody(req, config.viewerMaxMb * 1024 * 1024)
        if (bytes.subarray(0, 5).toString('latin1') !== '%PDF-') return sendJson(res, 400, { error: 'not a PDF' })
        const id = createHash('sha256').update(bytes).digest('hex')
        await mkdir(docs, { recursive: true })
        const file = join(docs, `${id}.pdf`)
        if (!(await exists(file))) await writeFile(file, bytes)
        return sendJson(res, 200, { id })
      }
      const match = /^\/documents\/([a-f0-9]+)\/pages\/(\d+)$/.exec(path)
      if (match && ID.test(match[1])) {
        const [, id, pageText] = match
        if (!(await exists(join(docs, `${id}.pdf`)))) return sendJson(res, 404, { error: 'unknown document' })
        const options = {
          langIn: url.searchParams.get('lang_in') || config.langIn,
          langOut: url.searchParams.get('lang_out') || config.langOut,
          service: url.searchParams.get('service') || config.service,
          kernel: url.searchParams.get('kernel') || config.kernel,
        }
        const closed = new AbortController()
        res.on('close', () => { if (!res.writableFinished) closed.abort() })
        const bytes = await translatePage(id, Number(pageText), options, closed.signal)
        res.writeHead(200, { 'content-type': 'application/pdf', 'cache-control': 'no-store' })
        return res.end(bytes)
      }
      return sendJson(res, 404, { error: 'not found' })
    } catch (error) {
      if (res.headersSent || res.destroyed) return
      return sendJson(res, 500, { error: error?.message ?? String(error) })
    }
  }
}

function sameOrigin(req) {
  const origin = req.headers.origin
  if (!origin) return true
  try {
    return new URL(origin).host === req.headers.host
  } catch {
    return false
  }
}

async function serveStatic(res, root, relative) {
  const file = normalize(join(root, relative))
  if (!file.startsWith(root + sep) || !TYPES[extname(file)] || !(await exists(file))) {
    return sendJson(res, 404, { error: 'not found' })
  }
  res.writeHead(200, { 'content-type': TYPES[extname(file)], 'cache-control': 'max-age=86400' })
  createReadStream(file).pipe(res)
}

function sendJson(res, status, value) {
  res.writeHead(status, { 'content-type': 'application/json' })
  res.end(JSON.stringify(value))
}

function readBody(req, limit) {
  return new Promise((resolve, reject) => {
    const chunks = []
    let size = 0
    req.on('data', (chunk) => {
      size += chunk.length
      if (size > limit) {
        reject(new Error('document is too large'))
        req.destroy()
      } else {
        chunks.push(chunk)
      }
    })
    req.on('end', () => resolve(Buffer.concat(chunks)))
    req.on('error', reject)
  })
}

async function exists(file) {
  try {
    await stat(file)
    return true
  } catch {
    return false
  }
}
