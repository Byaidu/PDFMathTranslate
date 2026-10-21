# Zotero

A Zotero 7+ plugin with two ways to translate:

- **In the PDF reader, as you scroll.** Press **译** (Tr) in the reader toolbar: pages coming into view, plus the next two, are translated and drawn over the originals one by one. Press it again to see the original.
- **Whole files from the item menu.** Right-click an item or PDF attachment → **Translate PDF with pdf2zh**; the translated and bilingual PDFs are added next to the original.

Both send their translations to one resident `pdf2zh --worker` process ([protocol](../README.md#pdf2zh---worker)): it starts on the first translation, so Python and the layout model load once, and stops after 10 minutes unused or when the plugin shuts down. Nothing has to be started by hand.

| File | Purpose |
| --- | --- |
| [`manifest.json`](manifest.json), [`bootstrap.js`](bootstrap.js) | Plugin id and Zotero's startup hooks |
| [`pdf2zh.js`](pdf2zh.js) | Item menu, the worker client (`WorkerClient`, started with Zotero's `Subprocess`), shared helpers |
| [`reader.js`](reader.js) | Reader toolbar button, page queue, cache |
| [`content.js`](content.js) | Runs inside the reader's pdf.js viewer: reports visible pages, draws translated pages |
| [`prefs.js`](prefs.js), [`prefs.xhtml`](prefs.xhtml) | Settings: command, languages, service, kernel, reader batch size |
| [`test.mjs`](test.mjs), [`test/fake-worker.mjs`](test/fake-worker.mjs) | Node tests for the helpers and the worker client, plus one real pdf2zh run |
| [`test/run-in-zotero.mjs`](test/run-in-zotero.mjs), [`test/harness/`](test/harness/) | End-to-end test in a throwaway Zotero profile |

## How reading works

1. The toolbar button injects `content.js` into the reader's pdf.js viewer. It reports the visible pages and draws, inside each page, a layer showing the translated page; the layer ignores the mouse, so links and annotations underneath keep working.
2. `reader.js` asks the pdf2zh worker for those pages. One translation runs at a time; pages requested while it runs are translated together next (pages "3,4,5" in one request, up to `readerBatch`), and pages that scrolled away before their turn are dropped.
3. Results are kept in the Zotero data directory under `pdf2zh/<file hash>/<options>/`, so reopening a PDF shows its translated pages at once. Changing the target language in the settings starts a new set.

The reader integration uses Zotero's documented `renderToolbar` hook plus the reader's internal pdf.js objects (`reader._internalReader._primaryView._iframeWindow.PDFViewerApplication`), which Zotero may change between versions.

## Build and install

```bash
pip install pdf2zh        # or: uv tool install pdf2zh
cd examples/zotero
zip -r ../pdf2zh-zotero.xpi manifest.json bootstrap.js pdf2zh.js reader.js content.js prefs.js prefs.xhtml
```

In Zotero: Tools → Plugins → gear menu → Install Plugin From File, and pick `pdf2zh-zotero.xpi`. Zotero is a GUI app and may not see your shell's PATH: if it cannot find pdf2zh, set the full path (for example `/Users/me/.local/bin/pdf2zh`) or `uvx pdf2zh` in Settings → pdf2zh.

## Test

```bash
node --test examples/zotero/test.mjs
PDF2ZH_BIN=$(which pdf2zh) node --test examples/zotero/test.mjs   # also runs one real translation through a worker

# End to end in a real Zotero, without touching your library: a throwaway
# profile and data directory, a second Zotero instance, no window.
ZOTERO_HEADLESS=1 PDF2ZH_BIN=$(which pdf2zh) node examples/zotero/test/run-in-zotero.mjs paper.pdf
```

The end-to-end test imports the PDF, opens it in the reader, presses the button, waits for the first translated page, jumps to the last page, waits for it too, and saves PNGs of each original and translated page.

## Status

- **Reader**, end to end in Zotero 10.0.6 (headless, isolated profile) on a 3-page PDF with the legacy kernel: the first page was drawn about 5 s after pressing the button, including the worker's start; after jumping to the end, pages 2–3 were translated in one batch and drawn 1.5 s later. No worker process was left after Zotero quit. The saved images show the translated pages at the originals' size, figures included.
- **Helpers and worker client:** Node tests pass, against a stand-in worker (reuse, errors, idle stop, restart after a crash, an old pdf2zh) and a real pdf2zh worker.
- **Not yet tested:** clicking the button with a mouse in a visible Zotero window (the test clicks it from code), how the button looks in the toolbar, and the item-menu command.

The plugin needs a pdf2zh release with `--worker`; until it is on PyPI, install pdf2zh from this repository. [zotero-pdf2zh](https://github.com/guaguastandup/zotero-pdf2zh) is the full-featured community plugin.
