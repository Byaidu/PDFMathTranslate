# Integration examples

Working starting points for building on pdf2zh. Each folder has its own README with setup steps and what has been tested.

| Folder | Client | How it talks to pdf2zh |
| --- | --- | --- |
| [`server/`](server/) | Any HTTP client, your own service | Python API (`pdf2zh.get_kernel`), exposed as REST + SSE and remote MCP |
| [`web/`](web/) | Browsers | The example server's REST API |
| [`claude/`](claude/) | Claude Desktop, Claude Code, claude.ai | MCP: local STDIO, or the example server's `/mcp` |
| [`chatgpt/`](chatgpt/) | ChatGPT | The example server's `/mcp` |
| [`zotero/`](zotero/) | Zotero 7+ | Subprocess: `pdf2zh <file> --json` |
| [`dsh/`](dsh/) | DeepSeek Harness | MCP over STDIO, as a dsh bundle |

## Which interface to use

| You are building | Use |
| --- | --- |
| A Python program | `from pdf2zh import get_kernel, TranslateRequest` |
| A plugin in another language that runs on the user's machine | `pdf2zh <file> --json`: one JSON line on stdout, logs on stderr, exit code 1 on failure |
| Something for an AI agent | `pdf2zh --mcp` (the host starts it) |
| A web app or a cloud service | The [example server](server/), or your own built the same way |

Prefer these over importing BabelDOC or pdf2zh internals: they are the interfaces this repository keeps stable.

`pdf2zh --json` prints:

```json
{"ok": true, "kernel": "babeldoc", "results": [{"input": "paper.pdf", "mono": "/abs/paper.zh.mono.pdf", "dual": "/abs/paper.zh.dual.pdf"}]}
```

or, on failure, `{"ok": false, "error": "…"}` with exit code 1.
