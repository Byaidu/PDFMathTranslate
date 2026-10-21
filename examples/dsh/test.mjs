// Tests for the dsh-pdf2zh plugin: npm install && npm test
// Set PDF2ZH_BIN to a pdf2zh executable to also run a real translation.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { copyFileSync, existsSync, mkdtempSync, realpathSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import * as plugin from './index.js'

const here = dirname(fileURLToPath(import.meta.url))
const fake = (mode) => `"${process.execPath}" "${join(here, 'test-fake-worker.mjs')}" ${mode}`

/** Load the plugin into a stand-in ctx; returns the tool, with a dispose(). */
function load(config = {}) {
  let tool
  const disposers = []
  const ctx = {
    tools: { register: (t) => { tool = t } },
    get: () => undefined,
    inject: () => {},
    effect: (fn) => disposers.push(fn()),
  }
  plugin.apply(ctx, plugin.Config(config))
  tool.dispose = () => disposers.forEach(d => d())
  return tool
}

function scratch() {
  const dir = mkdtempSync(join(tmpdir(), 'dsh-pdf2zh-'))
  const file = join(dir, 'in.pdf')
  writeFileSync(file, '%PDF-1.4 fake')
  return { dir, file }
}

test('plugin declares its name, dependencies and defaults', () => {
  assert.equal(plugin.name, 'pdf2zh')
  assert.deepEqual(plugin.inject, ['tools'])
  const config = plugin.Config({})
  assert.equal(config.command, 'pdf2zh')
  assert.equal(config.kernel, 'auto')
  assert.equal(config.idleMinutes, 10)
  assert.throws(() => plugin.Config({ kernel: 'fast' }))
})

test('registers pdf2zh_translate with a file parameter', () => {
  const tool = load()
  assert.equal(tool.name, 'pdf2zh_translate')
  assert.deepEqual(tool.parameters.required, ['file'])
  const text = tool.output.render({}, { kernel: 'babeldoc', mono: '/a.mono.pdf' })[0].text
  assert.match(text, /a\.mono\.pdf/)
  tool.dispose()
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
  tool.dispose()
})

test('translateParams maps the plugin options to worker params', () => {
  const params = plugin.translateParams('/p.pdf', '/out', { langIn: 'en', langOut: 'ja', service: 'deepl', kernel: 'auto', pages: '1-2' })
  assert.deepEqual(params, { file: '/p.pdf', output: '/out', lang_in: 'en', lang_out: 'ja', service: 'deepl', kernel: 'auto', pages: '1-2' })
  assert.equal('pages' in plugin.translateParams('/p.pdf', '/out', {}), false)
  assert.deepEqual(plugin.splitCommand('uvx  pdf2zh'), ['uvx', 'pdf2zh'])
})

test('the tool translates through one worker until the plugin is disposed', async () => {
  const { dir, file } = scratch()
  const tool = load({ command: fake('ok') })
  try {
    const first = await tool.execute({ file, output_dir: dir }, {})
    const second = await tool.execute({ file, output_dir: dir }, {})
    assert.equal(first.mono, join(dir, 'out.mono.pdf'))
    assert.equal(first.kernel, 'legacy')
    assert.equal(second.kernel, 'legacy')
  } finally {
    tool.dispose()
  }
})

test('worker: one process, errors, abort, timeout, restart after a crash', async () => {
  const { dir, file } = scratch()
  const worker = new plugin.Pdf2zhWorker({ command: fake('ok') })
  try {
    const a = await worker.translate({ file, output: dir })
    const b = await worker.translate({ file, output: dir })
    assert.equal(a.pid, b.pid)

    await assert.rejects(worker.translate({ file, output: dir, fail: 'quota exceeded' }), /quota exceeded/)

    const controller = new AbortController()
    const slow = worker.translate({ file, output: dir, delay: 5_000 }, { signal: controller.signal })
    setTimeout(() => controller.abort(new Error('stop')), 20)
    await assert.rejects(slow, /stop/)
    await assert.rejects(worker.translate({ file, output: dir, delay: 5_000 }, { timeoutMs: 50 }), /did not finish/)

    const exited = new Promise(r => worker.child.once('exit', r))
    worker.child.kill()
    await exited
    const c = await worker.translate({ file, output: dir })
    assert.notEqual(c.pid, a.pid)
  } finally {
    worker.close()
  }
})

test('worker stops after being idle and starts again on demand', async () => {
  const { dir, file } = scratch()
  const worker = new plugin.Pdf2zhWorker({ command: fake('ok'), idleMs: 50 })
  try {
    const a = await worker.translate({ file, output: dir })
    await new Promise(r => setTimeout(r, 150))
    assert.equal(worker.child, null)
    const b = await worker.translate({ file, output: dir })
    assert.notEqual(a.pid, b.pid)
  } finally {
    worker.close()
  }
})

test('worker failures give actionable errors', async () => {
  const { dir, file } = scratch()
  const cases = [
    ['pdf2zh-does-not-exist', /Cannot find "pdf2zh-does-not-exist"/],
    [fake('old'), /too old for the plugin/],
    [fake('crash'), /worker exited with 3/],
  ]
  for (const [command, message] of cases) {
    const worker = new plugin.Pdf2zhWorker({ command })
    await assert.rejects(worker.translate({ file, output: dir }), message)
    worker.close()
  }
})

test('real translation through the tool', { skip: !process.env.PDF2ZH_BIN, timeout: 600_000 }, async () => {
  const dir = mkdtempSync(join(tmpdir(), 'dsh-pdf2zh-'))
  const pdf = join(dir, 'paper.pdf')
  copyFileSync(join(here, '..', '..', 'test', 'file', 'translate.cli.plain.text.pdf'), pdf)
  const tool = load({ command: process.env.PDF2ZH_BIN })
  try {
    const value = await tool.execute({ file: pdf, lang_out: 'zh' }, { signal: AbortSignal.timeout(590_000) })
    assert.ok(existsSync(value.mono), value.mono)
    assert.ok(existsSync(value.dual), value.dual)
    assert.equal(realpathSync(dirname(value.mono)), realpathSync(dir))  // written next to the input
  } finally {
    tool.dispose()
  }
})
