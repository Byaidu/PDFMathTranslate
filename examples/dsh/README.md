# DeepSeek Harness (dsh)

A native dsh plugin, `dsh-pdf2zh`, that gives the model a `pdf2zh_translate` tool. It is plain ESM JavaScript with no build step:

| File | Purpose |
| --- | --- |
| [`index.js`](index.js) | The plugin: settings schema and the `pdf2zh_translate` tool |
| [`cordis.patch.yml`](cordis.patch.yml) | The bundle layer that enables the plugin |
| [`package.json`](package.json) | Declares the bundle (`"dsh": { "bundle": … }`) |
| [`test.mjs`](test.mjs) | Node tests, plus one real translation |

The tool runs `pdf2zh <file> --json` as a subprocess and reads the single JSON line pdf2zh prints on stdout. Relative paths start in the session's workspace; the translated (mono) and bilingual (dual) PDFs are written next to the input unless `output_dir` is given. A cancelled tool call stops pdf2zh.

## Install

Install pdf2zh first (`pip install pdf2zh` or `uv tool install pdf2zh`), then add the plugin to a dsh profile:

```bash
cd examples/dsh && npm pack            # builds dsh-pdf2zh-0.1.0.tgz
dsh plugin --profile web add ./dsh-pdf2zh-0.1.0.tgz
```

`dsh plugin` needs pnpm on PATH. Once the package is on npm, `dsh plugin --profile web add dsh-pdf2zh` works too. Remove it with `dsh plugin --profile web remove dsh-pdf2zh`.

## Settings

Override the row in your profile's `cordis.patch.yml`:

```yaml
- id: tool-pdf2zh
  config:
    command: /Users/me/.local/bin/pdf2zh   # or "uvx pdf2zh"
    langOut: ja
    service: openai:gpt-4o-mini            # API keys come from the environment
    kernel: auto                           # auto, babeldoc or legacy
    timeoutMs: 1800000
```

dsh started from the Dock may not see your shell's PATH; the plugin also searches `~/.local/bin`, `/opt/homebrew/bin` and `/usr/local/bin`, and `command` takes a full path.

## Test

```bash
cd examples/dsh && npm install && npm test
PDF2ZH_BIN=$(which pdf2zh) npm test      # also runs one real translation
```

## Status

Tested with dsh 0.2.1-rc.2 (web app) and pdf2zh from this branch:

- Loaded through `--patch`, the model called `pdf2zh_translate` and both PDFs were written next to the input.
- Packed with `npm pack` and installed with `dsh plugin add`: the plugin is listed under installed plugins and its component runs, with Schemastery provided by dsh.
- The Node tests pass, including a real translation.

Not yet tested: the DeepSeek Harness desktop app and an npm install. The tool needs a pdf2zh release with `--json`; until it is on PyPI, install pdf2zh from this repository.

pdf2zh also ships an MCP server (`pdf2zh --mcp`); dsh can use it through `@deepseek-ai/dsh-mcp-client` instead of this plugin.
