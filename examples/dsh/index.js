// dsh-pdf2zh: a native DeepSeek Harness plugin that translates PDFs with pdf2zh.
//
// Host half (this file):
// - the pdf2zh_translate tool;
// - the PDF reader's HTTP routes (viewer.js), which translate pages on demand.
// Both send their translations to one resident `pdf2zh --worker` process
// (pdf2zh.js), started on first use and stopped when idle or on dispose.
// Browser half (client.js): a PDF reader for dsh's right-sidebar document
// preview that requests translated pages as they scroll into view.
//
// Plain JavaScript, no build step.

import { dirname, isAbsolute, resolve } from 'node:path'
import Schema from '@deepseek-ai/schemastery'
import { Pdf2zhWorker, translateParams } from './pdf2zh.js'
import { createViewer } from './viewer.js'

export { Pdf2zhWorker, searchPath, splitCommand, translateParams } from './pdf2zh.js'

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
  viewerBatch: Schema.natural().min(1).default(4)
    .description('PDF reader: most pages translated by one pdf2zh run.'),
  viewerMaxMb: Schema.natural().min(1).default(200)
    .description('PDF reader: largest document it accepts, in MB.'),
  idleMinutes: Schema.natural().default(10)
    .description('Stop the background pdf2zh worker after this many idle minutes (0: keep it).'),
})

// ------------------------------------------------------------------ plugin

export function apply(ctx, config) {
  const worker = new Pdf2zhWorker({ command: config.command, idleMs: config.idleMinutes * 60_000 })
  ctx.effect(() => () => worker.close())
  const translate = (params, signal) => worker.translate(params, { signal, timeoutMs: config.timeoutMs })

  // The reader's routes need dsh's web server, present in Web and Desktop.
  ctx.inject(['webServer'], (ctx) => {
    const handler = createViewer(config, { translate })
    ctx.effect(() => ctx.webServer.register({ kind: 'prefix', path: '/pdf2zh', handler }))
  })

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
      const result = await translate(translateParams(file, outputDir, {
        langIn: args.lang_in || config.langIn,
        langOut: args.lang_out || config.langOut,
        service: args.service || config.service,
        kernel: args.kernel || config.kernel,
        pages: args.pages,
      }), exec?.signal)
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
