"""PDF reader for MCP Apps hosts (Claude, ChatGPT, ...).

`open_pdf_reader` shows ui://pdf2zh/reader.html in the conversation. The
reader asks for pages as they scroll into view through the app-only tool
`get_pdf_page`, which returns one page as a JPEG: the original rendered with
PyMuPDF, or the translated page. Only one page crosses the wire per call, so
large PDFs stay within hosts' tool-result limits.

Each kernel run has seconds of fixed cost, so runs cover several pages: the
pages requested while a translation runs, plus the uncached pages after them
(hosts may send the reader's calls one at a time, so the server reads ahead
itself). The first run of a document translates only what was asked, to show
the first page soon; opening a document starts translating page 1 at once.
Translated pages are cached on disk per document and options.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import json
import os
import sys
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, TypedDict

from mcp import types

READER_URI = "ui://pdf2zh/reader.html"
READER_HTML = Path(__file__).with_name("mcp_reader.html")
# The reader loads the MCP Apps SDK from this CDN; hosts allow only listed domains.
CDN = "https://unpkg.com"
MAX_DOWNLOAD = 200 * 1024 * 1024


class ReaderDocument(TypedDict):
    doc_id: str
    title: str
    page_count: int
    page_sizes: list[list[float]]
    lang_in: str
    lang_out: str
    service: str
    kernel: str


def cache_root() -> Path:
    return Path(os.environ.get("PDF2ZH_READER_CACHE") or Path(tempfile.gettempdir()) / "pdf2zh-reader")


def options_key(options: dict) -> str:
    raw = json.dumps([options.get(k) for k in ("lang_in", "lang_out", "service", "kernel")])
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class _Job:
    doc_id: str
    key: str
    options: dict
    page: int
    futures: list = field(default_factory=list)


class PageTranslator:
    """Translate pages one kernel run at a time, batching pages that wait."""

    def __init__(self, translate, batch: int = 4):
        self.translate = translate  # async (doc_id, options, pages) -> {page: pdf path}
        self.batch = batch
        self.pending: list[_Job] = []
        self.running = False

    async def page(self, doc_id: str, options: dict, page: int) -> Path:
        key = options_key(options)
        job = next(
            (j for j in self.pending if (j.doc_id, j.key, j.page) == (doc_id, key, page)),
            None,
        )
        if job is None:
            job = _Job(doc_id, key, options, page)
            self.pending.append(job)
        future = asyncio.get_running_loop().create_future()
        job.futures.append(future)
        asyncio.get_running_loop().call_soon(self._pump)
        return await future

    def _pump(self) -> None:
        if self.running:
            return
        # Drop jobs whose callers went away (cancelled tool calls).
        for job in self.pending:
            job.futures = [f for f in job.futures if not f.done()]
        self.pending = [j for j in self.pending if j.futures]
        if not self.pending:
            return
        first = self.pending[0]
        jobs = [
            j for j in self.pending if (j.doc_id, j.key) == (first.doc_id, first.key)
        ][: self.batch]
        self.pending = [j for j in self.pending if j not in jobs]
        self.running = True
        asyncio.get_running_loop().create_task(self._run(first, jobs))

    async def _run(self, first: _Job, jobs: list[_Job]) -> None:
        try:
            files = await self.translate(
                first.doc_id, first.options, sorted(j.page for j in jobs)
            )
            for job in jobs:
                for f in job.futures:
                    if not f.done():
                        f.set_result(files[job.page])
        except Exception as e:  # report to every waiting page
            for job in jobs:
                for f in job.futures:
                    if not f.done():
                        f.set_exception(e)
        finally:
            self.running = False
            self._pump()


class Reader:
    """Documents opened in the reader and their translated pages."""

    def __init__(self, root: Optional[Path] = None, kernel_factory=None, batch: int = 4):
        self.root = root or cache_root()
        self.docs: dict[str, Path] = {}
        self.batch = batch
        self._kernel_factory = kernel_factory
        self._kernels: dict[str, object] = {}
        self._running: dict[tuple, asyncio.Future] = {}  # (doc_id, key, page) -> run
        self._prefetches: set[asyncio.Task] = set()
        self.translator = PageTranslator(self._translate, batch=batch)

    # ------------------------------------------------------------- documents

    def open(self, source: str) -> dict:
        """Register a local path or http(s) URL; returns the document summary."""
        (self.root / "documents").mkdir(parents=True, exist_ok=True)
        if source.startswith(("http://", "https://")):
            data = _download(source)
            title = Path(urllib.parse.urlparse(source).path).name or "document.pdf"
        else:
            path = Path(source).expanduser()
            if not path.is_file():
                raise FileNotFoundError(f"no such file: {source}")
            data = path.read_bytes()
            title = path.name
        if not data.startswith(b"%PDF-"):
            raise ValueError("not a PDF")
        doc_id = hashlib.sha256(data).hexdigest()
        file = self.root / "documents" / f"{doc_id}.pdf"
        if not file.exists():
            file.write_bytes(data)
        self.docs[doc_id] = file

        import pymupdf

        with pymupdf.open(file) as doc:
            sizes = [[round(p.rect.width, 2), round(p.rect.height, 2)] for p in doc]
        return {"doc_id": doc_id, "title": title, "page_count": len(sizes), "page_sizes": sizes}

    def prefetch(self, doc_id: str, options: dict, page: int = 1) -> None:
        """Start translating `page` in the background, before the reader asks."""

        async def run():
            with contextlib.suppress(Exception):
                await self.translated_page(doc_id, page, options)

        task = asyncio.get_running_loop().create_task(run())
        self._prefetches.add(task)
        task.add_done_callback(self._prefetches.discard)

    def path(self, doc_id: str) -> Path:
        file = self.docs.get(doc_id) or self.root / "documents" / f"{doc_id}.pdf"
        if not file.is_file():
            raise ValueError("unknown document; open it with open_pdf_reader first")
        return file

    # ------------------------------------------------------------- pages

    async def image(self, doc_id: str, page: int, width: int, translated: bool, options: dict) -> bytes:
        """One page as JPEG bytes, `width` pixels wide."""
        if translated:
            source = await self.translated_page(doc_id, page, options)
        else:
            source = self.path(doc_id)
        return await asyncio.to_thread(_render, source, page, width)

    async def translated_page(self, doc_id: str, page: int, options: dict) -> Path:
        index = self._index(doc_id, options)
        cached = index.get(str(page))
        if cached and (self._dir(doc_id, options) / cached).is_file():
            return self._dir(doc_id, options) / cached
        running = self._running.get((doc_id, options_key(options), page))
        if running is not None:  # part of a run that is already going
            return (await asyncio.shield(running))[page]
        return await self.translator.page(doc_id, options, page)

    async def _translate(self, doc_id: str, options: dict, pages: list[int]) -> dict[int, Path]:
        from pdf2zh.kernel.protocol import TranslateRequest

        key = options_key(options)
        index = self._index(doc_id, options)
        if index:  # not the first run: read ahead
            pages = self._read_ahead(doc_id, key, index, pages)
        run = asyncio.get_running_loop().create_future()
        run.add_done_callback(lambda f: f.cancelled() or f.exception())  # no "never retrieved"
        for p in pages:
            self._running[(doc_id, key, p)] = run
        try:
            files = await self._translate_pages(doc_id, options, pages)
            run.set_result(files)
            return files
        except Exception as e:
            run.set_exception(e)
            raise
        finally:
            for p in pages:
                self._running.pop((doc_id, key, p), None)

    def _read_ahead(self, doc_id: str, key: str, index: dict, pages: list[int]) -> list[int]:
        import pymupdf

        with pymupdf.open(self.path(doc_id)) as doc:
            count = doc.page_count
        pages = list(pages)
        p = max(pages)
        while len(pages) < self.batch and p < count:
            p += 1
            if str(p) not in index and (doc_id, key, p) not in self._running:
                pages.append(p)
        return pages

    async def _translate_pages(self, doc_id: str, options: dict, pages: list[int]) -> dict[int, Path]:
        from pdf2zh.kernel.protocol import TranslateRequest

        out = self._dir(doc_id, options) / f"run-{'-'.join(map(str, pages))}"
        out.mkdir(parents=True, exist_ok=True)
        kernel = self._kernel(options.get("kernel") or "auto")
        request = TranslateRequest(
            files=[str(self.path(doc_id))],
            lang_in=options.get("lang_in") or "en",
            lang_out=options.get("lang_out") or "zh",
            service=options.get("service") or "google",
            pages=[p - 1 for p in pages],
            output=str(out),
            no_dual=True,
        )
        # In STDIO mode stdout carries the MCP protocol; keep kernel output off it.
        # The kernel runs in a worker thread: BabelDOC does CPU-heavy work
        # inside its async API, which would otherwise stall page renders.
        with contextlib.redirect_stdout(sys.stderr):
            results = await asyncio.to_thread(kernel.translate, request, lambda *a: None)
        if not results or not results[0].mono_pdf:
            raise RuntimeError("translation produced no PDF")
        mono = Path(results[0].mono_pdf)
        index = self._index(doc_id, options)
        for p in pages:
            index[str(p)] = f"{out.name}/{mono.name}"
        (self._dir(doc_id, options) / "index.json").write_text(json.dumps(index))
        return {p: mono for p in pages}

    def _kernel(self, name: str):
        if name not in self._kernels:
            if self._kernel_factory:
                self._kernels[name] = self._kernel_factory(name)
            else:
                from pdf2zh.kernel import get_kernel

                self._kernels[name] = get_kernel(name)
        return self._kernels[name]

    def _dir(self, doc_id: str, options: dict) -> Path:
        return self.root / "pages" / doc_id / options_key(options)

    def _index(self, doc_id: str, options: dict) -> dict:
        try:
            return json.loads((self._dir(doc_id, options) / "index.json").read_text())
        except (OSError, ValueError):
            return {}


def _render(file: Path, page: int, width: int) -> bytes:
    import pymupdf

    with pymupdf.open(file) as doc:
        if not 1 <= page <= doc.page_count:
            raise ValueError(f"page {page} is out of range 1-{doc.page_count}")
        p = doc[page - 1]
        zoom = max(0.2, min(width, 2400) / p.rect.width)
        pix = p.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        return pix.tobytes("jpeg", jpg_quality=85)


def _download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read(MAX_DOWNLOAD + 1)
    if len(data) > MAX_DOWNLOAD:
        raise ValueError("document is too large")
    return data


def register(mcp, reader: Optional[Reader] = None) -> Reader:
    """Add the reader's resource and tools to an MCP server."""
    reader = reader or Reader()
    ui_meta = {"ui": {"resourceUri": READER_URI}, "ui/resourceUri": READER_URI}

    @mcp.resource(
        READER_URI,
        name="pdf2zh reader",
        mime_type="text/html;profile=mcp-app",
        meta={"ui": {"csp": {"resourceDomains": [CDN]}, "prefersBorder": True}},
    )
    def reader_html() -> str:
        return READER_HTML.read_text(encoding="utf-8")

    @mcp.tool(meta=ui_meta)
    async def open_pdf_reader(
        file: str,
        lang_out: str = "zh",
        lang_in: str = "en",
        service: str = "google",
        kernel: str = "auto",
    ) -> ReaderDocument:
        """Open a PDF in an interactive reader that translates pages as the user
        scrolls, keeping formulas, figures and layout. `file` is an absolute
        path on this machine or an http(s) URL. `lang_in` / `lang_out` are
        language codes such as en, zh, ja; `service` is a translation service
        such as google, deepl or openai:gpt-4o-mini."""
        summary = await asyncio.to_thread(reader.open, file)
        options = {"lang_in": lang_in, "lang_out": lang_out, "service": service, "kernel": kernel}
        reader.prefetch(summary["doc_id"], options)
        return {**summary, **options}

    @mcp.tool(meta={"ui": {"visibility": ["app"]}})
    async def get_pdf_page(
        doc_id: str,
        page: int,
        width: int = 900,
        translated: bool = False,
        lang_out: str = "zh",
        lang_in: str = "en",
        service: str = "google",
        kernel: str = "auto",
    ) -> list[types.ImageContent]:
        """One page of a document opened with open_pdf_reader, as a JPEG; with
        translated=true, the translated page (translated on first request)."""
        options = {"lang_in": lang_in, "lang_out": lang_out, "service": service, "kernel": kernel}
        data = await reader.image(doc_id, page, width, translated, options)
        return [types.ImageContent(type="image", data=base64.b64encode(data).decode(), mimeType="image/jpeg")]

    return reader
