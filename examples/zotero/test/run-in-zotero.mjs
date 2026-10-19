// End-to-end check of the reader in a real Zotero, without touching your own
// library: creates a throwaway profile and data directory, installs the
// plugin and test/harness from this checkout, starts a second Zotero
// instance, and checks the harness report.
//
//   PDF2ZH_BIN=$(which pdf2zh) node test/run-in-zotero.mjs [file.pdf]
//
// Needs Zotero 7+ (ZOTERO_APP overrides /Applications/Zotero.app on macOS).
// ZOTERO_HEADLESS=1 runs Zotero without a window.
import { spawn } from 'node:child_process'
import { existsSync, mkdirSync, mkdtempSync, openSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const plugin = resolve(here, '..')
const pdf = resolve(process.argv[2] || join(plugin, '..', '..', 'test', 'file', 'translate.cli.plain.text.pdf'))
const bin = process.env.PDF2ZH_BIN
const app = process.env.ZOTERO_APP || '/Applications/Zotero.app/Contents/MacOS/zotero'
if (!bin) throw new Error('set PDF2ZH_BIN to a pdf2zh executable with --json')

const root = mkdtempSync(join(tmpdir(), 'pdf2zh-zotero-'))
const profile = join(root, 'profile')
const data = join(root, 'data')
const out = join(root, 'out')
for (const dir of [profile, data, out, join(profile, 'extensions')]) mkdirSync(dir, { recursive: true })
writeFileSync(join(profile, 'extensions', 'pdf2zh@pdfmathtranslate.github.io'), plugin)
writeFileSync(join(profile, 'extensions', 'pdf2zh-harness@pdfmathtranslate.github.io'), join(here, 'harness'))
const prefs = {
  'extensions.zotero.dataDir': data,
  'extensions.zotero.useDataDir': true,
  'extensions.zotero.firstRun2': false,
  'extensions.autoDisableScopes': 0,
  'xpinstall.signatures.required': false,
  'extensions.pdf2zh.command': bin,
  'extensions.pdf2zh.langOut': process.env.PDF2ZH_LANG_OUT || 'zh',
}
writeFileSync(join(profile, 'user.js'),
  Object.entries(prefs).map(([k, v]) => `user_pref(${JSON.stringify(k)}, ${JSON.stringify(v)});`).join('\n') + '\n')

console.log(`profile: ${root}`)
const started = Date.now()
const args = ['-no-remote', '-profile', profile]
if (process.env.ZOTERO_HEADLESS) args.push('--headless') // no window on screen
args.push('-ZoteroDebugText') // Zotero's debug output, saved to out/zotero.log
const log = openSync(join(out, 'zotero.log'), 'w')
const child = spawn(app, args, {
  env: { ...process.env, PDF2ZH_TEST_OUT: out, PDF2ZH_TEST_PDF: pdf },
  stdio: ['ignore', log, log],
})
const timeout = setTimeout(() => child.kill(), 15 * 60 * 1000)
await new Promise(r => child.on('exit', r))
clearTimeout(timeout)

const reportPath = join(out, 'report.json')
if (!existsSync(reportPath)) {
  console.error('Zotero exited without a report')
  process.exit(1)
}
const report = JSON.parse(readFileSync(reportPath, 'utf8'))
for (const s of report.steps) console.log(`${((s.t - started) / 1000).toFixed(1).padStart(6)}s  ${s.name}${s.pages ? ' ' + s.pages.join(',') : ''}`)
console.log(report.ok ? `ok: translated pages ${report.translatedPages.join(',')} of ${report.total}` : `failed: ${report.error}`)
console.log(`images and zotero.log: ${out}`)
process.exit(report.ok ? 0 : 1)
