// Stand-in for `pdf2zh --worker` in test.mjs: `node test/fake-worker.mjs <mode> --worker`.
//   ok      translate copies params.file to <output>/out.mono.pdf (params.delay ms later)
//   old     an old pdf2zh without --worker: argparse error, exit 2
//   crash   exits on the first translate request
import { copyFileSync } from 'node:fs'
import { join } from 'node:path'
import { createInterface } from 'node:readline'

const mode = process.argv[2]
if (mode === 'old') {
  process.stderr.write('usage: pdf2zh [-h] ...\npdf2zh: error: unrecognized arguments: --worker\n')
  process.exit(2)
}
const send = (message) => process.stdout.write(JSON.stringify(message) + '\n')
console.log('a stray line that is not JSON')
send({ ready: true, protocol: 1, version: 'fake', kernels: ['legacy'], pid: process.pid })
const timers = new Map()
createInterface({ input: process.stdin }).on('line', (line) => {
  const { id, method, params = {} } = JSON.parse(line)
  if (method === 'cancel') {
    clearTimeout(timers.get(params.id))
    send({ id: params.id, error: { message: 'cancelled', cancelled: true } })
    send({ id, result: { ok: true } })
  } else if (method === 'translate') {
    if (mode === 'crash') process.exit(3)
    if (params.fail) return send({ id, error: { message: params.fail, cancelled: false } })
    timers.set(id, setTimeout(() => {
      const mono = join(params.output, 'out.mono.pdf')
      copyFileSync(params.file, mono)
      send({ id, result: { ok: true, kernel: 'legacy', pid: process.pid, results: [{ input: params.file, mono, dual: null }] } })
    }, params.delay ?? 0))
  }
})
