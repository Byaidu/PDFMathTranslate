// Unit tests for the plugin's plain-JavaScript helpers: node --test test.mjs
// Set PDF2ZH_BIN to a pdf2zh executable to also run one real translation.
import { test } from "node:test";
import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdtempSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const PDF2ZH = createRequire(import.meta.url)("./pdf2zh.js");
const here = dirname(fileURLToPath(import.meta.url));

test("splitCommand handles launchers and quoted paths", () => {
  assert.deepEqual(PDF2ZH.splitCommand("pdf2zh"), ["pdf2zh"]);
  assert.deepEqual(PDF2ZH.splitCommand("uvx  pdf2zh"), ["uvx", "pdf2zh"]);
  assert.deepEqual(PDF2ZH.splitCommand('"C:\\My Tools\\pdf2zh.exe"'), ["C:\\My Tools\\pdf2zh.exe"]);
  assert.deepEqual(PDF2ZH.splitCommand(""), []);
});

test("buildArgs asks for JSON output in the given directory", () => {
  const args = PDF2ZH.buildArgs("/a b/paper.pdf", "/tmp/out", { langOut: "ja", service: "deepl" });
  assert.equal(args[0], "/a b/paper.pdf");
  assert.deepEqual(args.slice(args.indexOf("--lang-out"), args.indexOf("--lang-out") + 2), ["--lang-out", "ja"]);
  assert.ok(args.includes("--json"));
  assert.equal(args[args.indexOf("--output") + 1], "/tmp/out");
  assert.equal(args[args.indexOf("--kernel") + 1], "auto");
});

test("parseResult takes the last JSON result line", () => {
  const out = 'noise\n{"ok": true, "kernel": "babeldoc", "results": [{"mono": "/m.pdf", "dual": "/d.pdf"}]}\n';
  assert.equal(PDF2ZH.parseResult(out).results[0].dual, "/d.pdf");
  assert.equal(PDF2ZH.parseResult('{"ok": false, "error": "boom"}').error, "boom");
  assert.throws(() => PDF2ZH.parseResult("Traceback ..."), /no result/);
});

test("extraPath covers uv and Homebrew locations", () => {
  assert.ok(PDF2ZH.extraPath("/Users/me", false).includes("/Users/me/.local/bin"));
  assert.ok(PDF2ZH.extraPath("C:\\Users\\me", true)[0].endsWith("\\.local\\bin"));
});

test("real pdf2zh run matches what the plugin parses", { skip: !process.env.PDF2ZH_BIN, timeout: 600_000 }, async () => {
  const out = mkdtempSync(join(tmpdir(), "pdf2zh-zotero-"));
  const pdf = join(here, "..", "..", "test", "file", "translate.cli.plain.text.pdf");
  const args = PDF2ZH.buildArgs(pdf, out, { kernel: process.env.PDF2ZH_KERNEL || "auto" });
  const stdout = await new Promise((resolve, reject) =>
    execFile(process.env.PDF2ZH_BIN, args, { maxBuffer: 1 << 26 }, (err, so) => (err ? reject(err) : resolve(so))),
  );
  const result = PDF2ZH.parseResult(stdout);
  assert.equal(result.ok, true);
  assert.ok(existsSync(result.results[0].mono));
  assert.ok(existsSync(result.results[0].dual));
});
