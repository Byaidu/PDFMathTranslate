// dsh-pdf2zh: a native DeepSeek Harness plugin that translates PDFs with pdf2zh.
//
// It registers one tool, pdf2zh_translate, which runs `pdf2zh <file> --json`
// as a subprocess. pdf2zh prints exactly one JSON line on stdout
// ({"ok": true, "results": [{"mono": ..., "dual": ...}]}) and logs on stderr.
//
// Plain ESM JavaScript, no build step. The only import beyond Node is
// Schemastery, which dsh provides to plugins, for the settings form.

import { spawn } from 'node:child_process'
import { homedir } from 'node:os'
import { delimiter, dirname, isAbsolute, join, resolve } from 'node:path'
import Schema from '@deepseek-ai/schemastery'

export const name = 'pdf2zh'
export const inject = ['tools']

export const Config = Schema.object({
  command: Schema.string().default('pdf2zh')
    .description('Command that starts pdf2zh: `pdf2zh`, `uvx pdf2zh`, or an absolute path.'),
  langIn: Schema.string().default('en').description('Default source language code.'),
  langOut: Schema.string().default('zh').description('Default target language code.'),
  service: Schema.string().default('google')
    .description('Default translation service, optionally service:model, e.g. openai:gpt-4o-mini.'),
  kernel: Schema.union(['auto', 'babeldoc', 'legacy']).default('auto')
    .description('Translation kernel.'),
  timeoutMs: Schema.natural().default(30 * 60 * 1000)
    .description('Give up on one translation after this many milliseconds.'),
})

// ------------------------------------------------------------------ helpers

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

// ------------------------------------------------------------------ plugin

export function apply(ctx, config) {
  ctx.tools.register({
    name: 'pdf2zh_translate',
    description:
      'Translate a PDF, DOC or DOCX file with pdf2zh and keep its formulas, figures and layout. '
      + 'Writes a translated PDF (mono) and a bilingual PDF (dual) next to the input, or into '
      + 'output_dir, and returns their paths. Takes one to several minutes.',
    parameters: {
      type: 'object',
      properties: {
        file: { type: 'string', description: 'Path to the document; relative paths start in the workspace' },
        lang_out: { type: 'string', description: `Target language code, default ${config.langOut}` },
        lang_in: { type: 'string', description: `Source language code, default ${config.langIn}` },
        service: { type: 'string', description: `Translation service, default ${config.service}` },
        kernel: { type: 'string', enum: ['auto', 'babeldoc', 'legacy'], description: `Kernel, default ${config.kernel}` },
        pages: { type: 'string', description: '1-based pages to translate, e.g. "1,3-5"; default all' },
        output_dir: { type: 'string', description: 'Directory for the results; default the input file\'s directory' },
      },
      required: ['file'],
    },
    output: {
      schema: {
        type: 'object',
        // dsh accepts one type string per property, so absent paths are
        // omitted rather than null.
        properties: {
          kernel: { type: 'string' },
          mono: { type: 'string', description: 'Translated PDF' },
          dual: { type: 'string', description: 'Bilingual PDF' },
        },
        required: ['kernel'],
      },
      render: (_args, value) => [{
        type: 'text',
        text: `Translated with the ${value.kernel} kernel.\n`
          + `Translated PDF: ${value.mono ?? '(none)'}\nBilingual PDF: ${value.dual ?? '(none)'}`,
      }],
    },
    async execute(args, exec) {
      if (typeof args.file !== 'string' || !args.file.trim()) throw new Error('file is required')
      const base = await workingDirectory(ctx, exec)
      const file = isAbsolute(args.file) ? args.file : resolve(base, args.file)
      const outputDir = args.output_dir
        ? (isAbsolute(args.output_dir) ? args.output_dir : resolve(base, args.output_dir))
        : dirname(file)
      const result = await runPdf2zh(config.command, buildArgs(file, outputDir, {
        langIn: args.lang_in || config.langIn,
        langOut: args.lang_out || config.langOut,
        service: args.service || config.service,
        kernel: args.kernel || config.kernel,
        pages: args.pages,
      }), { signal: exec?.signal, timeoutMs: config.timeoutMs })
      if (!result.ok) throw new Error(result.error || 'pdf2zh failed')
      const first = result.results?.[0] ?? {}
      return {
        kernel: result.kernel,
        ...(first.mono ? { mono: first.mono } : {}),
        ...(first.dual ? { dual: first.dual } : {}),
      }
    },
  })
}

/** The session's working directory when dsh provides one, else the process cwd. */
async function workingDirectory(ctx, exec) {
  const service = ctx.get?.('workingDirectory')
  if (service && exec?.agent !== undefined) {
    try {
      return await service.ensure(exec.agent, exec.signal)
    } catch {
      // fall through
    }
  }
  return process.cwd()
}
