# Claude

Three ways to give Claude the pdf2zh tools. All of them use the MCP server that ships with pdf2zh; nothing here needs its own code.

| Client | Use | Files are read from |
| --- | --- | --- |
| Claude Desktop | [`claude_desktop_config.json`](claude_desktop_config.json) | your computer |
| Claude Code | the [`pdf2zh` plugin](pdf2zh/) or one command | your computer |
| claude.ai (web, mobile) | a custom connector to the [example server](../server/) | a public URL |

The `uvx --from pdf2zh[mcp]` commands below need a pdf2zh release that includes the unified entry point. Until it is on PyPI, replace `pdf2zh[mcp]` with `pdf2zh[mcp] @ git+https://github.com/PDFMathTranslate/PDFMathTranslate` or with the path of a local checkout.

## Claude Desktop

Merge [`claude_desktop_config.json`](claude_desktop_config.json) into Claude Desktop's config file (Settings → Developer → Edit Config), then restart Claude Desktop. Claude starts `pdf2zh --mcp` on demand; [uv](https://docs.astral.sh/uv/) must be installed.

Try: *"Translate ~/Downloads/paper.pdf into Chinese."*

## Claude Code

Quickest, one command:

```bash
claude mcp add pdf2zh -- uvx --from "pdf2zh[mcp]" pdf2zh --mcp
```

Or install the plugin, which adds the MCP server and a `translate-pdf` skill that tells Claude how to call it:

```
# inside Claude Code, from a clone of this repository
/plugin marketplace add ./examples/claude
/plugin install pdf2zh@pdf2zh
```

The plugin is [`pdf2zh/`](pdf2zh/): `.claude-plugin/plugin.json` (manifest), `.mcp.json` (the MCP server) and `skills/translate-pdf/SKILL.md`. Copy it as the starting point for your own plugin.

## claude.ai custom connector

claude.ai runs in the cloud and cannot read files on your computer, so it needs a server it can reach over HTTPS:

1. Run the [example server](../server/) and expose it with a tunnel, for example `cloudflared tunnel --url http://127.0.0.1:7861`.
2. Restart the server with the tunnel's address:
   `PDF2ZH_PUBLIC_URL=https://<tunnel-host> PDF2ZH_ALLOWED_HOSTS=<tunnel-host> python examples/server/server.py`
3. In claude.ai, add a custom connector with the URL `https://<tunnel-host>/mcp` (Settings → Connectors).

Claude then has `translate_pdf_url`, which takes a PDF link and returns download links for the translation.

## Status

The MCP server, its tools and the remote `/mcp` endpoint are tested with the MCP Python SDK (stdio and Streamable HTTP, mcp 1.21 and 2.3). The Claude Code plugin files follow the documented layout but have not been loaded in Claude Code, and the Claude Desktop and claude.ai steps have not been run against those apps.
