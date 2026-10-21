# DeepSeek Harness (dsh)

`dsh-pdf2zh` is a native dsh plugin with two parts:

- **A PDF reader that translates as you scroll.** PDFs opened in dsh's right sidebar show the original and the translation side by side; pages are translated when they come into view and appear one by one.
- **A `pdf2zh_translate` tool** the model can call to translate a whole file.

Plain JavaScript, no build step:

| File | Half | Purpose |
| --- | --- | --- |
| [`index.js`](index.js) | Host | Settings, the `pdf2zh_translate` tool, mounts the reader's routes |
| [`viewer.js`](viewer.js) | Host | Reader routes under `/pdf2zh`, page queue, cache |
| [`pdf2zh.js`](pdf2zh.js) | Host | Client for the resident `pdf2zh --worker` process |
| [`client.js`](client.js) | Browser | The reader: a document preview for `.pdf` in the right sidebar |
| [`cordis.patch.yml`](cordis.patch.yml), [`package.json`](package.json) | — | Bundle and client declarations |
| [`test.mjs`](test.mjs), [`test-viewer.mjs`](test-viewer.mjs), [`test-fake-worker.mjs`](test-fake-worker.mjs) | — | Node tests, and a stand-in worker for them |

## How the reader works

1. Opening a `.pdf` in the right sidebar selects the reader: it registers a document preview with `priority: 'extension'`, which ranks above the built-in PDF viewer. The preview's viewer menu still offers the built-in one.
2. The reader renders pages with pdf.js, which the plugin serves from its own dependency at `/pdf2zh/pdfjs/`, and uploads the file once to `/pdf2zh/documents` (stored by SHA-256).
3. Pages entering the viewport, plus the next two, are requested from `/pdf2zh/documents/<id>/pages/<n>`. Requests for pages that scroll away before their turn are withdrawn.
4. The host sends one translation at a time to a resident `pdf2zh --worker` process. Pages requested while it runs are translated together in the next request (up to `viewerBatch`), so a document streams in with one kernel run per batch, and Python and the layout model load only once. Each page is cut out with pdf-lib and cached by document, page, language, service and kernel, so reopening or switching back is instant.

Modes: **原文 / Original**, **译文 / Translated**, **对照 / Side by side**; a target-language menu; and **自动翻译 / Auto-translate**, which can be turned off in favour of a "translate visible pages" button.

The routes have no dsh login check of their own: non-GET requests must carry an `x-pdf2zh: 1` header and come from the same origin, uploads must be PDFs, and the reader never takes file paths.

## The pdf2zh worker

The tool and the reader share one `pdf2zh --worker` process ([protocol](../README.md#pdf2zh---worker)). It starts on the first translation, stops after `idleMinutes` without one, and stops when dsh unloads or reloads the plugin; it also exits by itself if dsh quits, since its stdin closes. If it crashes, the next translation starts a new one. An old pdf2zh without `--worker` gets a message saying to update it.

## Install

Install pdf2zh first (`pip install pdf2zh` or `uv tool install pdf2zh`), then add the plugin to a dsh profile:

```bash
cd examples/dsh && npm pack            # builds dsh-pdf2zh-0.1.0.tgz
dsh plugin --profile web add ./dsh-pdf2zh-0.1.0.tgz
```

`dsh plugin` needs pnpm on PATH; pnpm installs pdfjs-dist and pdf-lib. Once the package is on npm, `dsh plugin --profile web add dsh-pdf2zh` works too. Remove it with `dsh plugin --profile web remove dsh-pdf2zh`.

## Settings

Override the row in your profile's `cordis.patch.yml`:

```yaml
- id: tool-pdf2zh
  name: dsh-pdf2zh
  config:
    command: /Users/me/.local/bin/pdf2zh   # or "uvx pdf2zh"
    langOut: ja                            # the reader's default target language too
    service: openai:gpt-4o-mini            # API keys come from the environment
    kernel: auto                           # auto, babeldoc or legacy
    viewerBatch: 4                         # most pages per pdf2zh run in the reader
    idleMinutes: 10                        # stop the pdf2zh worker after this long unused; 0 keeps it
```

dsh started from the Dock may not see your shell's PATH; the plugin also searches `~/.local/bin`, `/opt/homebrew/bin` and `/usr/local/bin`, and `command` takes a full path. Reader caches live in the system temp folder under `dsh-pdf2zh/`.

## Test

```bash
cd examples/dsh && npm install && npm test
PDF2ZH_BIN=$(which pdf2zh) npm test      # also runs one real translation through a worker
```

## Status

Tested with dsh 0.2.1-rc.2 (web app) and pdf2zh from this branch:

- **Reader:** installed from `npm pack` with `dsh plugin add`, it took over a 3-page PDF opened from the workspace file tree. Page 1 was translated first, pages 2–3 arrived together in the next batch, and switching to Japanese in translation-only mode requested pages only as they were scrolled to. No console errors.
- **Tool:** the model called `pdf2zh_translate` and both PDFs were written next to the input.
- **Desktop app:** the DeepSeek Harness desktop app loads the plugin from a linked checkout; with the profile's `hmr` entry watching the plugin folder, edits apply within a second.
- **Node tests:** host routes (against a stub translator), the page queue, page splitting, the browser half's registration, and the worker client against a stand-in worker (reuse, errors, abort, timeout, idle stop, restart after a crash, an old pdf2zh). A real translation through a real worker runs when `PDF2ZH_BIN` is set.

Not yet tested: an npm install. With a warm worker, a legacy run takes about 3 s for 1–3 pages; the first run after start also loads the layout model. The plugin needs a pdf2zh release with `--worker`; until it is on PyPI, install pdf2zh from this repository.

pdf2zh also ships an MCP server (`pdf2zh --mcp`); dsh can use it through `@deepseek-ai/dsh-mcp-client` instead of this plugin's tool.
