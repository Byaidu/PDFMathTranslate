// Unit tests for the plugin's plain-JavaScript helpers: node --test test.mjs
// Set PDF2ZH_BIN to a pdf2zh executable to also run a real translation.
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtempSync, existsSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const PDF2ZH = createRequire(import.meta.url)("./pdf2zh.js");
const here = dirname(fileURLToPath(import.meta.url));

/** What PDF2ZH.startWorker does in Zotero, with Node's child_process. */
function nodeStart(command, args) {
  return (onLine, onExit) => {
    const child = spawn(command, [...args, "--worker"], { stdio: ["pipe", "pipe", "pipe"] });
    let stderr = "";
    child.stderr.setEncoding("utf8").on("data", (c) => { stderr += c; });
    child.stdin.on("error", () => {});
    createInterface({ input: child.stdout }).on("line", onLine);
    child.on("error", (e) => onExit(e.code, stderr));
    child.on("close", (code) => onExit(code, stderr));
    return { pid: child.pid, write: (text) => child.stdin.write(text), close: () => child.stdin.end() };
  };
}
const fake = (mode) => nodeStart(process.execPath, [join(here, "test", "fake-worker.mjs"), mode]);

function scratch() {
  const dir = mkdtempSync(join(tmpdir(), "pdf2zh-zotero-"));
  const file = join(dir, "in.pdf");
  writeFileSync(file, "%PDF-1.4 fake");
  return { dir, file };
}

test("splitCommand handles launchers and quoted paths", () => {
  assert.deepEqual(PDF2ZH.splitCommand("pdf2zh"), ["pdf2zh"]);
  assert.deepEqual(PDF2ZH.splitCommand("uvx  pdf2zh"), ["uvx", "pdf2zh"]);
  assert.deepEqual(PDF2ZH.splitCommand('"C:\\My Tools\\pdf2zh.exe"'), ["C:\\My Tools\\pdf2zh.exe"]);
  assert.deepEqual(PDF2ZH.splitCommand(""), []);
});

test("translateParams fills defaults and passes reader page ranges", () => {
  assert.deepEqual(PDF2ZH.translateParams("/a b/paper.pdf", "/tmp/out", { langOut: "ja", service: "deepl" }), {
    file: "/a b/paper.pdf", output: "/tmp/out", lang_in: "en", lang_out: "ja", service: "deepl", kernel: "auto",
  });
  assert.equal(PDF2ZH.translateParams("/p.pdf", "/out", { pages: "2,3" }).pages, "2,3");
});

test("wantedPages adds pages ahead of the viewport", () => {
  assert.deepEqual(PDF2ZH.wantedPages([4, 3], 10, 2), [3, 4, 5, 6]);
  assert.deepEqual(PDF2ZH.wantedPages([10], 10, 2), [10]);
  assert.deepEqual(PDF2ZH.wantedPages([], 10, 2), []);
});

test("optionsKey is a safe directory name per option set", () => {
  const key = PDF2ZH.optionsKey({ langIn: "en", langOut: "zh", service: "openai:gpt-4o/mini", kernel: "auto" });
  assert.equal(key, "en--zh--openai_gpt-4o_mini--auto");
  assert.notEqual(key, PDF2ZH.optionsKey({ langIn: "en", langOut: "ja", service: "google", kernel: "auto" }));
});

test("extraPath covers uv and Homebrew locations", () => {
  assert.ok(PDF2ZH.extraPath("/Users/me", false).includes("/Users/me/.local/bin"));
  assert.ok(PDF2ZH.extraPath("C:\\Users\\me", true)[0].endsWith("\\.local\\bin"));
});

test("WorkerClient keeps one process, reports errors, restarts after it exits", async () => {
  const { dir, file } = scratch();
  const worker = new PDF2ZH.WorkerClient(fake("ok"));
  try {
    const a = await worker.translate({ file, output: dir });
    const b = await worker.translate({ file, output: dir });
    assert.equal(a.pid, b.pid);
    assert.equal(a.results[0].mono, join(dir, "out.mono.pdf"));
    await assert.rejects(worker.translate({ file, output: dir, fail: "quota exceeded" }), /quota exceeded/);

    process.kill(a.pid);
    await assert.rejects(worker.translate({ file, output: dir, delay: 5000 }), /worker exited|stopped/);
    const c = await worker.translate({ file, output: dir });
    assert.notEqual(c.pid, a.pid);
  } finally {
    worker.close();
  }
});

test("WorkerClient stops when idle and starts again on demand", async () => {
  const { dir, file } = scratch();
  const worker = new PDF2ZH.WorkerClient(fake("ok"), { idleMs: 50 });
  try {
    const a = await worker.translate({ file, output: dir });
    await new Promise((r) => setTimeout(r, 150));
    assert.equal(worker.transport, null);
    const b = await worker.translate({ file, output: dir });
    assert.notEqual(a.pid, b.pid);
  } finally {
    worker.close();
  }
});

test("WorkerClient explains an old pdf2zh and a crash", async () => {
  const { dir, file } = scratch();
  for (const [mode, message] of [["old", /too old for the plugin/], ["crash", /worker exited with 3/]]) {
    const worker = new PDF2ZH.WorkerClient(fake(mode));
    await assert.rejects(worker.translate({ file, output: dir }), message);
    worker.close();
  }
});

test("real translation through a pdf2zh worker", { skip: !process.env.PDF2ZH_BIN, timeout: 600_000 }, async () => {
  const out = mkdtempSync(join(tmpdir(), "pdf2zh-zotero-"));
  const pdf = join(here, "..", "..", "test", "file", "translate.cli.plain.text.pdf");
  const worker = new PDF2ZH.WorkerClient(nodeStart(process.env.PDF2ZH_BIN, []));
  try {
    const result = await worker.translate(
      PDF2ZH.translateParams(pdf, out, { kernel: process.env.PDF2ZH_KERNEL || "auto" }),
    );
    assert.equal(result.ok, true);
    assert.ok(existsSync(result.results[0].mono));
    assert.ok(existsSync(result.results[0].dual));
  } finally {
    worker.close();
  }
});
