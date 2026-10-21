# Example server

One Python file, [`server.py`](server.py), that serves:

| Path | For | What |
| --- | --- | --- |
| `/` | browsers | The [web frontend](../web/index.html) |
| `/api/...` | any HTTP client | Upload, live progress, download |
| `/mcp` | ChatGPT, claude.ai, other MCP hosts | Streamable HTTP MCP with `translate_pdf_url` and `list_kernels` |

It builds on the public Python API (`pdf2zh.get_kernel`, `TranslateRequest`), so it is also the reference for embedding pdf2zh in your own service.

## Run

```bash
pip install pdf2zh                   # includes MCP, Starlette and Uvicorn
python examples/server/server.py --port 7861
```

Open http://127.0.0.1:7861/.

| Variable | Default | Meaning |
| --- | --- | --- |
| `PDF2ZH_DATA_DIR` | a new temp directory | Where uploads and results are stored |
| `PDF2ZH_PUBLIC_URL` | `http://<host>:<port>` | Base of the download links the MCP tool returns |
| `PDF2ZH_ALLOWED_HOSTS` | localhost only | Extra host names `/mcp` accepts, comma-separated; `*` turns the check off |
| `PDF2ZH_MAX_MB` | `100` | Largest upload or download |

Translation services read their keys from the environment as usual, for example `OPENAI_API_KEY`.

## REST API

```bash
# start a job: multipart form with file, lang_in, lang_out, service, kernel, pages
curl -F file=@paper.pdf -F lang_out=zh http://127.0.0.1:7861/api/jobs
# -> {"id": "…", "state": "queued", "progress": 0.0, "files": {}, …}

curl http://127.0.0.1:7861/api/jobs/<id>               # status
curl -N http://127.0.0.1:7861/api/jobs/<id>/events     # server-sent events until done
curl -O http://127.0.0.1:7861/api/jobs/<id>/files/dual # result: mono or dual
curl http://127.0.0.1:7861/api/kernels                 # installed kernels
```

A job's `state` goes `queued` → `running` → `done` or `failed`; `progress` runs from 0 to 1 and `stage` names the current step. Jobs run one at a time.

## Limits

This is a prototype: no authentication, jobs kept in memory, and `translate_pdf_url` fetches any URL it is given. Keep it on localhost or behind a private tunnel; add authentication, URL restrictions and durable storage before exposing it.

## Status

Tested on mcp 1.21 and 2.3: the REST flow (upload, SSE progress, download, rejecting non-PDF uploads), the web frontend in a browser with both kernels, `/mcp` with the MCP Python SDK's Streamable HTTP client, and host checking (unknown hosts get 421).
