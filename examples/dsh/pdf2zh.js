// A resident `pdf2zh --worker` process, shared by the pdf2zh_translate tool
// and the PDF reader. Python, the kernels and the layout model load once; the
// worker is started on first use and stopped after it has been idle a while
// or when the plugin is disposed.
//
// Protocol (pdf2zh/worker.py): one JSON object per line. The worker first
// prints {"ready": true, "protocol": 1, ...}; then each request
// {"id", "method", "params"} gets one {"id", "result"} or {"id", "error"}.

import { spawn } from 'node:child_process'
import { homedir } from 'node:os'
import { delimiter, join } from 'node:path'
import { createInterface } from 'node:readline'

const PROTOCOL = 1

/** Split a command line such as `uvx pdf2zh` or `"C:\My Tools\pdf2zh.exe"`. */
export function splitCommand(line) {
  const parts = []
  const re = /"([^"]*)"|'([^']*)'|(\S+)/g
  let m
  while ((m = re.exec(line || ''))) parts.push(m[1] ?? m[2] ?? m[3])
  return parts
}

/** PATH plus the places uv, pip and Homebrew install commands. Apps started
 * from the Dock do not inherit the shell's PATH. */
export function searchPath(env = process.env, home = homedir(), platform = process.platform) {
  const extra = platform === 'win32'
    ? [join(home, '.local', 'bin'), join(home, 'AppData', 'Roaming', 'Python', 'Scripts')]
    : [join(home, '.local', 'bin'), '/opt/homebrew/bin', '/usr/local/bin']
  return [env.PATH, ...extra].filter(Boolean).join(delimiter)
}

/** Worker params for one translation; `options` uses the plugin's config names. */
export function translateParams(file, output, options) {
  return {
    file,
    output,
    lang_in: options.langIn,
    lang_out: options.langOut,
    service: options.service,
    kernel: options.kernel,
    ...(options.pages ? { pages: options.pages } : {}),
  }
}

export class Pdf2zhWorker {
  constructor({ command = 'pdf2zh', env = process.env, idleMs = 10 * 60_000, readyTimeoutMs = 120_000 } = {}) {
    this.command = command
    this.env = env
    this.idleMs = idleMs
    this.readyTimeoutMs = readyTimeoutMs
    this.child = null
    this.ready = null // Promise of the running worker's ready message
    this.pending = new Map() // id -> { resolve, reject }
    this.nextId = 1
    this.idleTimer = null
  }

  /** Translate with the worker; resolves with the `--json` result object. */
  async translate(params, { signal, timeoutMs } = {}) {
    signal?.throwIfAborted()
    this.#touch()
    const child = await this.#start()
    const id = this.nextId++
    return new Promise((resolvePromise, reject) => {
      const done = (fn, value) => {
        if (!this.pending.has(id)) return
        this.pending.delete(id)
        clearTimeout(timer)
        signal?.removeEventListener('abort', onAbort)
        if (this.pending.size === 0) this.#idleSoon()
        fn(value)
      }
      const cancel = (reason) => {
        this.#send(child, { id: this.nextId++, method: 'cancel', params: { id } })
        done(reject, reason)
      }
      const onAbort = () => cancel(signal.reason ?? new Error('aborted'))
      const timer = timeoutMs
        ? setTimeout(() => cancel(new Error(`pdf2zh did not finish within ${Math.round(timeoutMs / 1000)} s`)), timeoutMs)
        : undefined
      signal?.addEventListener('abort', onAbort, { once: true })
      this.pending.set(id, {
        resolve: (value) => done(resolvePromise, value),
        reject: (error) => done(reject, error),
      })
      this.#send(child, { id, method: 'translate', params })
    })
  }

  /** Stop the worker: close its stdin (it exits on EOF), then kill it if needed. */
  close() {
    clearTimeout(this.idleTimer)
    const child = this.child
    this.child = null
    this.ready = null
    this.#failAll(new Error('pdf2zh worker stopped'))
    if (!child) return
    child.stdin.end()
    setTimeout(() => child.kill(), 5_000).unref()
  }

  #start() {
    if (this.ready) return this.ready
    const [bin, ...prefix] = splitCommand(this.command)
    if (!bin) return Promise.reject(new Error('pdf2zh command is empty'))
    const child = spawn(bin, [...prefix, '--worker'], {
      env: { ...this.env, PATH: searchPath(this.env), PYTHONIOENCODING: 'utf-8' },
      stdio: ['pipe', 'pipe', 'pipe'],
      windowsHide: true,
    })
    this.child = child
    let stderr = ''
    child.stderr.setEncoding('utf8').on('data', (chunk) => { stderr = (stderr + chunk).slice(-20_000) })
    child.stdin.on('error', () => {}) // reported through 'exit'
    const lines = createInterface({ input: child.stdout })

    const ready = new Promise((resolveReady, rejectReady) => {
      const timer = setTimeout(() => {
        rejectReady(new Error('pdf2zh --worker did not start in time'))
        child.kill()
      }, this.readyTimeoutMs)
      let started = false
      lines.on('line', (line) => {
        let message
        try {
          message = JSON.parse(line)
        } catch {
          return // not protocol output
        }
        if (!started) {
          if (!message.ready) return
          started = true
          clearTimeout(timer)
          if (message.protocol !== PROTOCOL) {
            rejectReady(new Error(`pdf2zh worker speaks protocol ${message.protocol}; this plugin needs ${PROTOCOL}`))
            child.kill()
            return
          }
          resolveReady(child)
          return
        }
        const entry = this.pending.get(message.id)
        if (!entry) return
        if (message.error) {
          const error = new Error(message.error.message || 'pdf2zh failed')
          error.cancelled = Boolean(message.error.cancelled)
          entry.reject(error)
        } else {
          entry.resolve(message.result)
        }
      })
      const failed = (error) => {
        clearTimeout(timer)
        if (this.child === child) {
          this.child = null
          this.ready = null
        }
        rejectReady(error)
        this.#failAll(error)
      }
      child.on('error', (error) => failed(error.code === 'ENOENT'
        ? new Error(`Cannot find "${bin}". Install pdf2zh or set the plugin's command to its full path.`)
        : error))
      child.on('exit', (code, killedBy) => {
        const last = stderr.trim().split('\n').pop() || ''
        failed(new Error(/unrecognized arguments: .*--worker/.test(stderr)
          ? 'This pdf2zh is too old for the plugin: update pdf2zh to a version with --worker.'
          : `pdf2zh worker exited with ${killedBy ?? code}${last ? `: ${last}` : ''}`))
      })
    })
    ready.catch(() => {}) // callers see the rejection through translate()
    this.ready = ready
    return ready
  }

  #send(child, message) {
    if (child.stdin.writable) child.stdin.write(JSON.stringify(message) + '\n')
  }

  #failAll(error) {
    for (const entry of [...this.pending.values()]) entry.reject(error)
  }

  #touch() {
    clearTimeout(this.idleTimer)
  }

  #idleSoon() {
    clearTimeout(this.idleTimer)
    if (!this.idleMs) return
    this.idleTimer = setTimeout(() => this.close(), this.idleMs)
    this.idleTimer.unref()
  }
}
