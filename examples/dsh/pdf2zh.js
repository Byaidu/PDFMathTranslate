// Run pdf2zh as a subprocess and read its --json result. Shared by the
// pdf2zh_translate tool and the PDF reader.

import { spawn } from 'node:child_process'
import { homedir } from 'node:os'
import { delimiter, join } from 'node:path'

/** Split a command line such as `uvx pdf2zh` or `"C:\My Tools\pdf2zh.exe"`. */
export function splitCommand(line) {
  const parts = []
  const re = /"([^"]*)"|'([^']*)'|(\S+)/g
  let m
  while ((m = re.exec(line || ''))) parts.push(m[1] ?? m[2] ?? m[3])
  return parts
}

/** Arguments for one translation, ending with --json. */
export function buildArgs(file, outputDir, options) {
  const args = [
    file,
    '--lang-in', options.langIn,
    '--lang-out', options.langOut,
    '--service', options.service,
    '--kernel', options.kernel,
    '--output', outputDir,
  ]
  if (options.pages) args.push('--pages', options.pages)
  args.push('--json')
  return args
}

/** The result object from pdf2zh --json stdout (the last JSON line). */
export function parseResult(stdout) {
  for (const line of String(stdout).trim().split(/\r?\n/).reverse()) {
    if (!line.startsWith('{')) continue
    try {
      const result = JSON.parse(line)
      if (typeof result.ok === 'boolean') return result
    } catch {
      // not the result line
    }
  }
  throw new Error('pdf2zh printed no result; update pdf2zh to a version with --json')
}

/** PATH plus the places uv, pip and Homebrew install commands. Apps started
 * from the Dock do not inherit the shell's PATH. */
export function searchPath(env = process.env, home = homedir(), platform = process.platform) {
  const extra = platform === 'win32'
    ? [join(home, '.local', 'bin'), join(home, 'AppData', 'Roaming', 'Python', 'Scripts')]
    : [join(home, '.local', 'bin'), '/opt/homebrew/bin', '/usr/local/bin']
  return [env.PATH, ...extra].filter(Boolean).join(delimiter)
}

/** Run pdf2zh and resolve with its parsed --json result. */
export function runPdf2zh(command, args, { signal, timeoutMs, env = process.env } = {}) {
  const [bin, ...prefix] = splitCommand(command)
  if (!bin) return Promise.reject(new Error('pdf2zh command is empty'))
  return new Promise((resolvePromise, reject) => {
    const child = spawn(bin, [...prefix, ...args], {
      env: { ...env, PATH: searchPath(env), PYTHONIOENCODING: 'utf-8' },
      stdio: ['ignore', 'pipe', 'pipe'],
      signal,
      windowsHide: true,
    })
    // Our own timer: spawn's `timeout` option keeps running when the
    // command fails to start.
    const timer = timeoutMs ? setTimeout(() => child.kill(), timeoutMs) : undefined
    let settled = false
    const settle = (fn, value) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      fn(value)
    }
    let stdout = ''
    let stderr = ''
    child.stdout.setEncoding('utf8').on('data', (chunk) => { stdout += chunk })
    child.stderr.setEncoding('utf8').on('data', (chunk) => { stderr = (stderr + chunk).slice(-20_000) })
    child.on('error', (error) => {
      settle(reject, error.code === 'ENOENT'
        ? new Error(`Cannot find "${bin}". Install pdf2zh or set the plugin's command to its full path.`)
        : error)
    })
    child.on('close', (code, killedBy) => {
      try {
        settle(resolvePromise, parseResult(stdout))
      } catch {
        const last = stderr.trim().split('\n').pop()
        settle(reject, new Error(`pdf2zh exited with ${killedBy ?? code}${last ? `: ${last}` : ''}`))
      }
    })
  })
}
