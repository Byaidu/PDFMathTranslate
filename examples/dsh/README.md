# DeepSeek Harness (dsh)

A dsh bundle that gives the model the pdf2zh tools. It is two files and no code:

- [`package.json`](package.json) declares the bundle with `"dsh": { "bundle": { "patch": "./cordis.patch.yml" } }`.
- [`cordis.patch.yml`](cordis.patch.yml) inserts one `@deepseek-ai/dsh-mcp-client` row that starts `pdf2zh --mcp` over STDIO.

dsh starts pdf2zh when the profile loads; nothing has to be kept running. The model sees `mcp__pdf2zh__translate_pdf` and `mcp__pdf2zh__list_kernels`. Translations take minutes, so the row raises `toolCallTimeoutMs` from the client's 60-second default to 30 minutes.

## Install

Requires [uv](https://docs.astral.sh/uv/) on PATH. From a clone of this repository:

```bash
dsh plugin --profile web add ./examples/dsh
```

Once the package is published to npm: `dsh plugin --profile web add dsh-pdf2zh`. To list it on the dsh Discover page, add it to a plugin market index; the package carries the `dsh-plugin` keyword.

Without installing a bundle, paste the row from [`cordis.patch.yml`](cordis.patch.yml) into your profile's own `cordis.patch.yml`.

The `uvx --from pdf2zh[mcp]` command needs a pdf2zh release that includes the unified entry point. Until it is on PyPI, use `pdf2zh[mcp] @ git+https://github.com/PDFMathTranslate/PDFMathTranslate` in `args`.

## Build on it

- A dsh plugin with its own UI (a reader panel, a Zotero view) can call the same MCP tools, or run `pdf2zh <file> --json` as a subprocess and read one JSON line from stdout.
- Keep pdf2zh as the translation engine instead of importing BabelDOC directly: BabelDOC's Python API is internal and changes without notice; pdf2zh's CLI, MCP tools and `pdf2zh.get_kernel()` are the supported surface.

## Status

The patch row and manifest follow dsh's documented bundle and `dsh-mcp-client` formats, and the MCP server they start is tested with the MCP Python SDK over STDIO. The bundle has not been loaded in dsh.
