// Tests for the dsh-pdf2zh plugin: npm install && npm test
// Set PDF2ZH_BIN to a pdf2zh executable to also run one real translation.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { copyFileSync, existsSync, mkdtempSync, realpathSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import * as plugin from './index.js'

const here = dirname(fileURLToPath(import.meta.url))

/** Load the plugin into a stand-in ctx and return the registered tool. */
function load(config = {}) {
  let tool
  const ctx = { tools: { register: (t) => { tool = t } }, get: () => undefined }
  plugin.apply(ctx, plugin.Config(config))
  return tool
}

test('plugin declares its name, dependencies and defaults', () => {
  assert.equal(plugin.name, 'pdf2zh')
  assert.deepEqual(plugin.inject, ['tools'])
  const config = plugin.Config({})
  assert.equal(config.command, 'pdf2zh')
  assert.equal(config.kernel, 'auto')
  assert.throws(() => plugin.Config({ kernel: 'fast' }))
})

test('registers pdf2zh_translate with a file parameter', () => {
  const tool = load()
  assert.equal(tool.name, 'pdf2zh_translate')
  assert.deepEqual(tool.parameters.required, ['file'])
  const text = tool.output.render({}, { kernel: 'babeldoc', mono: '/a.mono.pdf' })[0].text
  assert.match(text, /a\.mono\.pdf/)
})

test('schemas use only what the dsh tool registry accepts', () => {
  const tool = load()
  const check = (schema, path) => {
    assert.equal(typeof schema.type, 'string', `${path}.type must be one type string`)
    for (const [key, child] of Object.entries(schema.properties ?? {})) check(child, `${path}.${key}`)
    if (schema.items) check(schema.items, `${path}[]`)
  }
  check(tool.parameters, 'parameters')
  check(tool.output.schema, 'output')
})

test('buildArgs and parseResult follow the pdf2zh --json contract', () => {
  const args = plugin.buildArgs('/p.pdf', '/out', { langIn: 'en', langOut: 'ja', service: 'deepl', kernel: 'auto', pages: '1-2' })
  assert.deepEqual(args.slice(-3), ['--pages', '1-2', '--json'])
  assert.equal(args[args.indexOf('--output') + 1], '/out')
  assert.equal(plugin.parseResult('log\n{"ok": true, "kernel": "legacy", "results": []}').kernel, 'legacy')
  assert.throws(() => plugin.parseResult('Traceback'), /no result/)
  assert.deepEqual(plugin.splitCommand('uvx  pdf2zh'), ['uvx', 'pdf2zh'])
})

test('a missing command gives an actionable error', async () => {
  const tool = load({ command: 'pdf2zh-does-not-exist' })
  await assert.rejects(tool.execute({ file: '/tmp/x.pdf' }, {}), /Cannot find "pdf2zh-does-not-exist"/)
})

test('real translation through the tool', { skip: !process.env.PDF2ZH_BIN, timeout: 600_000 }, async () => {
  const dir = mkdtempSync(join(tmpdir(), 'dsh-pdf2zh-'))
  const pdf = join(dir, 'paper.pdf')
  copyFileSync(join(here, '..', '..', 'test', 'file', 'translate.cli.plain.text.pdf'), pdf)
  const tool = load({ command: process.env.PDF2ZH_BIN })
  const value = await tool.execute({ file: pdf, lang_out: 'zh' }, { signal: AbortSignal.timeout(590_000) })
  assert.ok(existsSync(value.mono), value.mono)
  assert.ok(existsSync(value.dual), value.dual)
  assert.equal(realpathSync(dirname(value.mono)), realpathSync(dir))  // written next to the input
})
