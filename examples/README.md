# Integration examples

Working starting points for building on pdf2zh. Each folder has its own README with setup steps and what has been tested.

| Folder | Client | How it talks to pdf2zh |
| --- | --- | --- |
| [`server/`](server/) | Any HTTP client, your own service | Python API (`pdf2zh.get_kernel`), exposed as REST + SSE and remote MCP |
| [`web/`](web/) | Browsers | The example server's REST API |
| [`claude/`](claude/) | Claude Desktop, Claude Code, claude.ai | MCP: local STDIO, or the example server's `/mcp` |
| [`chatgpt/`](chatgpt/) | ChatGPT | The example server's `/mcp` |
| [`zotero/`](zotero/) | Zotero 7+ | Reader that translates as you scroll, and an item-menu command; resident `pdf2zh --worker` |
| [`dsh/`](dsh/) | DeepSeek Harness | Native dsh plugin: a PDF reader that translates as you scroll, and a tool; resident `pdf2zh --worker` |

## Which interface to use

| You are building | Use |
| --- | --- |
| A Python program | `from pdf2zh import get_kernel, TranslateRequest` |
| A plugin in another language that runs on the user's machine | `pdf2zh --worker`: start it once, send JSON requests on stdin, read one JSON line per answer |
| A script that translates one file and exits | `pdf2zh <file> --json`: one JSON line on stdout, logs on stderr, exit code 1 on failure |
| Something for an AI agent | `pdf2zh --mcp` (the host starts it) |
| A web app or a cloud service | The [example server](server/), or your own built the same way |

Prefer these over importing BabelDOC or pdf2zh internals: they are the interfaces this repository keeps stable. None of them needs anything beyond `pip install pdf2zh`.

### `pdf2zh --worker`

A resident process: Python, the kernels and the layout model load once, so every translation after the first skips seconds of start-up. The plugin starts it when it first needs it, and stops it by closing its stdin (the worker exits on end of input, so it never outlives the plugin). One JSON object per line; logs go to stderr.

```text
worker -> plugin  {"ready": true, "protocol": 1, "version": "1.9.12", "kernels": ["legacy"]}
plugin -> worker  {"id": 1, "method": "translate", "params": {"file": "/abs/paper.pdf", "output": "/abs/out",
                   "lang_in": "en", "lang_out": "zh", "service": "google", "kernel": "auto", "pages": "1,3-5"}}
worker -> plugin  {"id": 1, "result": {"ok": true, "kernel": "legacy", "results": [{"input": "/abs/paper.pdf",
                   "mono": "/abs/out/paper-mono.pdf", "dual": "/abs/out/paper-dual.pdf"}]}}
plugin -> worker  {"id": 2, "method": "cancel", "params": {"id": 1}}
worker -> plugin  {"id": 1, "error": {"message": "cancelled", "cancelled": true}}
```

Translations run one at a time, in arrival order; cancelling drops a waiting request and stops a running one. Only `file` is required; `pages` is 1-based. Give each request its own `output` folder: two runs on the same file write files with the same names. [`dsh/pdf2zh.js`](dsh/pdf2zh.js) (Node) and the `WorkerClient` in [`zotero/pdf2zh.js`](zotero/pdf2zh.js) are complete clients, with idle shutdown and restart after a crash. The protocol is defined in [`pdf2zh/worker.py`](../pdf2zh/worker.py).

### `pdf2zh --json`

```json
{"ok": true, "kernel": "legacy", "results": [{"input": "paper.pdf", "mono": "/abs/paper-mono.pdf", "dual": "/abs/paper-dual.pdf"}]}
```

or, on failure, `{"ok": false, "error": "…"}` with exit code 1. The worker's `result` is this same object.
