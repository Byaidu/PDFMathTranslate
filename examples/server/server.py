"""Example pdf2zh server: web frontend, REST API with live progress, remote MCP.

One process serves three kinds of client:

- the web frontend in ../web, at /
- any HTTP client, through the REST API under /api
- ChatGPT, Claude and other MCP hosts, through Streamable HTTP MCP at /mcp

Run it with:

    pip install 'pdf2zh[mcp]'
    python examples/server/server.py --port 7861

This is a prototype. It has no authentication and keeps jobs in memory, so
keep it on localhost or behind a private tunnel or reverse proxy you control.
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import os
import re
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, StreamingResponse

try:  # mcp >= 2 renamed FastMCP to MCPServer
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from pdf2zh import TranslateRequest, available_kernels, get_kernel

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
DATA_DIR = Path(os.environ.get("PDF2ZH_DATA_DIR") or tempfile.mkdtemp(prefix="pdf2zh-"))
PUBLIC_URL = os.environ.get("PDF2ZH_PUBLIC_URL", "").rstrip("/")
MAX_BYTES = int(os.environ.get("PDF2ZH_MAX_MB", "100")) * 1024 * 1024
ALLOWED_SUFFIXES = {".pdf", ".doc", ".docx"}

# Translation is CPU- and memory-heavy: run one job at a time.
_worker_lock = asyncio.Lock()


@dataclass
class Job:
    id: str
    dir: Path
    filename: str
    state: str = "queued"  # queued, running, done, failed
    progress: float = 0.0
    stage: str = ""
    error: Optional[str] = None
    files: dict[str, Path] = field(default_factory=dict)
    changed: asyncio.Event = field(default_factory=asyncio.Event)
    task: Optional[asyncio.Task] = None

    def status(self) -> dict:
        return {
            "id": self.id,
            "filename": self.filename,
            "state": self.state,
            "progress": round(self.progress, 4),
            "stage": self.stage,
            "error": self.error,
            "files": {name: f"/api/jobs/{self.id}/files/{name}" for name in self.files},
        }

    def notify(self) -> None:
        self.changed.set()


JOBS: dict[str, Job] = {}


def _safe_name(name: str) -> str:
    stem, suffix = os.path.splitext(Path(name).name)
    stem = re.sub(r"[^\w.-]+", "_", stem).strip("._") or "document"
    return stem[:80] + suffix.lower()


def _new_job(filename: str) -> Job:
    job_id = uuid.uuid4().hex
    job_dir = DATA_DIR / job_id
    job_dir.mkdir(parents=True)
    job = Job(id=job_id, dir=job_dir, filename=_safe_name(filename))
    JOBS[job_id] = job
    return job


async def _run(
    job: Job,
    lang_in: str,
    lang_out: str,
    service: str,
    kernel: str,
    pages: Optional[str],
) -> None:
    loop = asyncio.get_running_loop()

    def on_progress(event) -> None:
        # BabelDOC sends dicts; the legacy kernel sends tqdm objects from a
        # worker thread.
        if isinstance(event, dict):
            if "overall_progress" not in event:
                return
            progress, stage = event["overall_progress"] / 100, event.get("stage")
        else:
            total = getattr(event, "total", 0) or 0
            progress = event.n / total if total else 0.0
            stage = getattr(event, "desc", "")

        def update() -> None:
            job.progress, job.stage = progress, stage or job.stage
            job.notify()

        loop.call_soon_threadsafe(update)

    async with _worker_lock:
        job.state = "running"
        job.notify()
        try:
            engine = get_kernel(kernel)
            request = TranslateRequest(
                files=[str(job.dir / job.filename)],
                lang_in=lang_in,
                lang_out=lang_out,
                service=service,
                pages=_parse_pages(pages),
                output=str(job.dir),
            )
            results = await engine.translate_async(request, callback=on_progress)
            for name in ("mono", "dual"):
                path = getattr(results[0], f"{name}_pdf")
                if path:
                    job.files[name] = Path(path)
            job.state, job.progress = "done", 1.0
        except Exception as e:  # report every failure to the client
            job.state, job.error = "failed", str(e) or type(e).__name__
        job.notify()


def _parse_pages(pages: Optional[str]) -> Optional[list[int]]:
    """Convert a 1-based "1,3-5" spec to 0-based page indexes."""
    if not pages:
        return None
    result = []
    for part in pages.split(","):
        start, _, end = part.strip().partition("-")
        result.extend(range(int(start) - 1, int(end or start)))
    return result


def _start(job: Job, **options) -> None:
    # Keep a reference so the task is not garbage-collected mid-run.
    job.task = asyncio.get_running_loop().create_task(_run(job, **options))


async def _wait(job: Job) -> None:
    while job.state not in ("done", "failed"):
        job.changed.clear()
        await job.changed.wait()


# ---------------------------------------------------------------- MCP tools


def _transport_security() -> TransportSecuritySettings:
    """Only localhost may call by default; PDF2ZH_ALLOWED_HOSTS widens it."""
    hosts = [h.strip() for h in os.environ.get("PDF2ZH_ALLOWED_HOSTS", "").split(",")]
    hosts = [h for h in hosts if h]
    if "*" in hosts:
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)
    hosts += ["127.0.0.1:*", "localhost:*"]
    origins = [f"http://{h}" for h in hosts] + [f"https://{h}" for h in hosts]
    return TransportSecuritySettings(allowed_hosts=hosts, allowed_origins=origins)


def _supports(func, name: str) -> bool:
    return name in inspect.signature(func).parameters


security = _transport_security()
# mcp 1.x takes transport security in the constructor, 2.x in streamable_http_app.
mcp = FastMCP(
    "pdf2zh",
    **(
        {"transport_security": security}
        if _supports(FastMCP.__init__, "transport_security")
        else {}
    ),
)


@mcp.tool()
async def translate_pdf_url(
    url: str,
    lang_out: str = "zh",
    lang_in: str = "en",
    service: str = "google",
    kernel: str = "auto",
    pages: Optional[str] = None,
) -> dict:
    """Translate a PDF available at a public http(s) URL, keeping its layout.

    Returns download links for the translated PDF (`mono`) and the bilingual
    PDF (`dual`). `lang_in`/`lang_out` are language codes such as en, zh, ja.
    `pages` is an optional 1-based list such as "1,3-5".
    """
    if not url.startswith(("http://", "https://")):
        raise ValueError("url must start with http:// or https://")
    name = Path(httpx.URL(url).path).name or "document.pdf"
    if Path(name).suffix.lower() not in ALLOWED_SUFFIXES:
        name += ".pdf"
    job = _new_job(name)
    async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            size = 0
            with open(job.dir / job.filename, "wb") as f:
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise ValueError("file is too large")
                    f.write(chunk)
    _start(
        job,
        lang_in=lang_in,
        lang_out=lang_out,
        service=service,
        kernel=kernel,
        pages=pages,
    )
    await _wait(job)
    if job.state == "failed":
        raise RuntimeError(job.error)
    base = PUBLIC_URL or "http://127.0.0.1:7861"
    return {name: base + link for name, link in job.status()["files"].items()}


@mcp.tool()
def list_kernels() -> list[str]:
    """Translation kernels installed on this server."""
    return available_kernels()


# ---------------------------------------------------------------- REST API


@mcp.custom_route("/", methods=["GET"])
async def index(request: Request):
    return FileResponse(WEB_DIR / "index.html")


@mcp.custom_route("/api/kernels", methods=["GET"])
async def kernels(request: Request):
    return JSONResponse({"kernels": available_kernels()})


@mcp.custom_route("/api/jobs", methods=["POST"])
async def create_job(request: Request):
    form = await request.form(max_part_size=MAX_BYTES)
    upload = form.get("file")
    if upload is None or not hasattr(upload, "read"):
        return JSONResponse({"error": "missing file"}, status_code=400)
    if Path(upload.filename or "").suffix.lower() not in ALLOWED_SUFFIXES:
        return JSONResponse({"error": "only PDF, DOC and DOCX"}, status_code=400)
    job = _new_job(upload.filename)
    (job.dir / job.filename).write_bytes(await upload.read())
    _start(
        job,
        lang_in=form.get("lang_in") or "en",
        lang_out=form.get("lang_out") or "zh",
        service=form.get("service") or "google",
        kernel=form.get("kernel") or "auto",
        pages=form.get("pages") or None,
    )
    return JSONResponse(job.status(), status_code=202)


@mcp.custom_route("/api/jobs/{job_id}", methods=["GET"])
async def get_job(request: Request):
    job = JOBS.get(request.path_params["job_id"])
    if job is None:
        return JSONResponse({"error": "unknown job"}, status_code=404)
    return JSONResponse(job.status())


@mcp.custom_route("/api/jobs/{job_id}/events", methods=["GET"])
async def job_events(request: Request):
    """Server-sent events: one `status` event per change until the job ends."""
    import json

    job = JOBS.get(request.path_params["job_id"])
    if job is None:
        return JSONResponse({"error": "unknown job"}, status_code=404)

    async def stream():
        while True:
            job.changed.clear()
            yield f"event: status\ndata: {json.dumps(job.status())}\n\n"
            if job.state in ("done", "failed"):
                return
            try:
                await asyncio.wait_for(job.changed.wait(), timeout=15)
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@mcp.custom_route("/api/jobs/{job_id}/files/{name}", methods=["GET"])
async def job_file(request: Request):
    job = JOBS.get(request.path_params["job_id"])
    path = job.files.get(request.path_params["name"]) if job else None
    if path is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=path.name,
        content_disposition_type="inline",  # lets the frontend preview it
    )


def create_app():
    if _supports(mcp.streamable_http_app, "transport_security"):
        return mcp.streamable_http_app(transport_security=security)
    return mcp.streamable_http_app()


if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7861)
    args = parser.parse_args()
    if not PUBLIC_URL:
        PUBLIC_URL = f"http://{args.host}:{args.port}"
    print(
        f"Web UI: http://{args.host}:{args.port}/  MCP: http://{args.host}:{args.port}/mcp"
    )
    uvicorn.run(create_app(), host=args.host, port=args.port)
