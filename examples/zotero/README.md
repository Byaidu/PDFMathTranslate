# Zotero

A Zotero 7+ plugin prototype. Right-click an item or a PDF attachment and choose **Translate PDF with pdf2zh**; the translated and bilingual PDFs are added next to the original.

It runs pdf2zh as a subprocess with `--json` and reads the single JSON line pdf2zh prints on stdout, so no server has to be kept running.

| File | Purpose |
| --- | --- |
| [`manifest.json`](manifest.json) | Plugin id, version and supported Zotero versions |
| [`bootstrap.js`](bootstrap.js) | Zotero's startup and window hooks |
| [`pdf2zh.js`](pdf2zh.js) | Menu, subprocess call, result parsing, attachment import |
| [`prefs.js`](prefs.js), [`prefs.xhtml`](prefs.xhtml) | Settings: command, languages, service, kernel |
| [`test.mjs`](test.mjs) | Node tests for the helpers, plus one real pdf2zh run |

## Build and install

```bash
pip install pdf2zh        # or: uv tool install pdf2zh
cd examples/zotero
zip -r ../pdf2zh-zotero.xpi manifest.json bootstrap.js pdf2zh.js prefs.js prefs.xhtml
```

In Zotero: Tools → Plugins → gear menu → Install Plugin From File, and pick `pdf2zh-zotero.xpi`. Zotero is a GUI app and may not see your shell's PATH: if it cannot find pdf2zh, set the full path (for example `/Users/me/.local/bin/pdf2zh`) or `uvx pdf2zh` in Settings → pdf2zh.

## Test

```bash
node --test examples/zotero/test.mjs
PDF2ZH_BIN=$(which pdf2zh) node --test examples/zotero/test.mjs   # also runs one real translation
```

## Status

The helper tests and a real pdf2zh run with the plugin's own arguments pass. The plugin has not been loaded in Zotero: the menu, the Subprocess call and the attachment import are untested there. [zotero-pdf2zh](https://github.com/guaguastandup/zotero-pdf2zh) is the full-featured community plugin; this prototype shows the minimal integration.
