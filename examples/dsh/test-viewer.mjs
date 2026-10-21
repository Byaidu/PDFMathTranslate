// Tests for the PDF reader: host routes, page queue, and the browser half's registration.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { copyFile, mkdtemp, readFile } from 'node:fs/promises'
import { createServer } from 'node:http'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { PDFDocument } from 'pdf-lib'
import { PageQueue, createViewer, splitPages } from './viewer.js'

const here = dirname(fileURLToPath(import.meta.url))

async function pdf(pageCount) {
  const doc = await PDFDocument.create()
  for (let i = 0; i < pageCount; i++) doc.addPage([200 + i, 300])
  return Buffer.from(await doc.save())
}

test('queue merges pages that wait during a run into one batch', async () => {
  const runs = []
  let release
  const gate = new Promise(r => { release = r })
  const queue = new PageQueue(async (id, options, pages) => {
    runs.push(pages)
    if (runs.length === 1) await gate
    return new Map(pages.map(p => [p, new Uint8Array([p])]))
  }, { batch: 3 })
  const opts = { langOut: 'zh' }
  const first = queue.request('a', opts, 1)
  await new Promise(r => setTimeout(r, 0))
  const later = [2, 3, 4, 5].map(p => queue.request('a', opts, p))
  release()
  assert.deepEqual([...(await first)], [1])
  assert.deepEqual((await Promise.all(later)).map(b => b[0]), [2, 3, 4, 5])
  assert.deepEqual(runs, [[1], [2, 3, 4], [5]])
})

test('queue drops a page whose only request was withdrawn', async () => {
  const runs = []
  const queue = new PageQueue(async (id, options, pages) => {
    runs.push(pages)
    return new Map(pages.map(p => [p, new Uint8Array([p])]))
  })
  const controller = new AbortController()
  const withdrawn = queue.request('a', {}, 7, controller.signal)
  controller.abort()
  await assert.rejects(withdrawn)
  await queue.request('a', {}, 8)
  assert.deepEqual(runs, [[8]])
})

test('queue reports a failed run to every waiting page', async () => {
  const queue = new PageQueue(async () => { throw new Error('pdf2zh broke') })
  await assert.rejects(queue.request('a', {}, 1), /pdf2zh broke/)
})

test('splitPages copies single pages', async () => {
  const pages = await splitPages(await pdf(3), [2, 3, 9])
  assert.deepEqual([...pages.keys()], [2, 3])
  const second = await PDFDocument.load(pages.get(2))
  assert.equal(second.getPageCount(), 1)
  assert.equal(second.getPage(0).getWidth(), 201)
})

test('routes: upload, translate a page, guards, static pdf.js', async () => {
  const runs = []
  // Stand-in for the pdf2zh worker: "translates" by copying the input.
  const translate = async (params) => {
    const out = join(params.output, 'out.mono.pdf')
    runs.push(params.pages)
    await copyFile(params.file, out)
    return { ok: true, kernel: 'legacy', results: [{ mono: out }] }
  }
  const config = { command: 'pdf2zh', langIn: 'en', langOut: 'zh', service: 'google', kernel: 'auto',
    timeoutMs: 60_000, viewerBatch: 4, viewerMaxMb: 10 }
  const handler = createViewer(config, { cacheDir: await mkdtemp(join(tmpdir(), 'pdf2zh-viewer-')), translate })
  const server = createServer(handler).listen(0, '127.0.0.1')
  await new Promise(r => server.once('listening', r))
  const base = `http://127.0.0.1:${server.address().port}/pdf2zh`
  const post = (path, body, headers = { 'x-pdf2zh': '1' }) => fetch(base + path, { method: 'POST', body, headers })
  try {
    assert.equal((await post('/documents', await pdf(2), {})).status, 403)
    assert.equal((await post('/documents', await pdf(2), { 'x-pdf2zh': '1', origin: 'http://evil.example' })).status, 403)
    assert.equal((await post('/documents', Buffer.from('hello'))).status, 400)

    const { id } = await (await post('/documents', await pdf(2))).json()
    assert.match(id, /^[a-f0-9]{64}$/)
    const page = await post(`/documents/${id}/pages/2?lang_out=ja`)
    assert.equal(page.status, 200)
    assert.equal(page.headers.get('content-type'), 'application/pdf')
    const single = await PDFDocument.load(new Uint8Array(await page.arrayBuffer()))
    assert.equal(single.getPageCount(), 1)
    assert.equal(single.getPage(0).getWidth(), 201)

    await post(`/documents/${id}/pages/2?lang_out=ja`) // cached: no second run
    assert.deepEqual(runs, ['2'])
    assert.equal((await post(`/documents/${'0'.repeat(64)}/pages/1`)).status, 404)

    const config = await (await fetch(`${base}/config`)).json()
    assert.equal(config.langOut, 'zh')
    const lib = await fetch(`${base}/pdfjs/build/pdf.min.mjs`)
    assert.equal(lib.status, 200)
    assert.equal(lib.headers.get('content-type'), 'text/javascript')
    await lib.arrayBuffer()
    assert.equal((await fetch(`${base}/pdfjs/..%2F..%2Fpackage.json`)).status, 404)
  } finally {
    server.close()
  }
})

test('client.js registers a PDF document preview', async () => {
  let factory
  globalThis.window = { __ModuleLoader__: { load: (entry) => { factory = entry.factory } } }
  const react = { createElement: () => null, useCallback: f => f, useEffect: () => {}, useMemo: f => f(),
    useRef: () => ({}), useState: v => [v, () => {}] }
  await import('./client.js')
  const plugin = factory(name => { assert.equal(name, 'react'); return react })
  assert.deepEqual(plugin.inject, ['slots', 'documentPreviews'])
  assert.deepEqual(plugin.wantedPages([5, 4], 10, 2), [4, 5, 6, 7])
  assert.deepEqual(plugin.wantedPages([9, 10], 10, 2), [9, 10])

  const registered = {}
  const ctx = {
    effect: fn => fn(),
    documentPreviews: { register: def => { registered.preview = def; return () => {} } },
    slots: {
      inject: (name, fn) => { registered.slot = name; return fn() },
      register: (entry, component) => { registered.entry = entry; registered.component = component; return () => {} },
    },
  }
  plugin.apply(ctx)
  assert.deepEqual(registered.preview.extensions, ['pdf'])
  assert.equal(registered.preview.priority, 'extension')
  assert.equal(registered.preview.loading, 'bytes-complete')
  assert.equal(registered.slot, 'sidebar.right.tab.document')
  assert.equal(registered.entry.key, registered.preview.id)
  assert.equal(typeof registered.component, 'function')
})
