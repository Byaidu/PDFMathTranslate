"""`pdf2zh --worker`: a resident pdf2zh process for apps and plugins.

A plugin starts one worker and keeps it while it needs translations, so Python,
the kernels and the layout model load once instead of once per run. The
protocol is one JSON object per line, over stdin and stdout; logs go to
stderr. It needs nothing beyond the standard library.

worker -> app, once at start:
    {"ready": true, "protocol": 1, "version": "1.9.12", "kernels": ["legacy"]}

app -> worker:
    {"id": 1, "method": "translate", "params": {
        "file": "/abs/paper.pdf", "output": "/abs/out",
        "lang_in": "en", "lang_out": "zh", "service": "google",
        "kernel": "auto", "pages": "1,3-5"}}
    {"id": 2, "method": "cancel", "params": {"id": 1}}
    {"id": 3, "method": "ping"}

worker -> app, one per request:
    {"id": 1, "result": {"ok": true, "kernel": "legacy",
                         "results": [{"input": ..., "mono": ..., "dual": ...}]}}
    {"id": 1, "error": {"message": "...", "cancelled": false}}

Translations run one at a time, in arrival order; a cancelled request that has
not started is dropped, a running one is asked to stop. `pages` is 1-based, as
on the command line ("1,3-5" or [1, 3, 4, 5]). The worker exits when stdin
closes, so it never outlives the app that started it.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import sys
import threading
from pathlib import Path
from typing import Any, Optional, TextIO

logger = logging.getLogger(__name__)

PROTOCOL = 1


def result_payload(kernel_name: str, files: list[str], results: list) -> dict:
    """The `--json` result object, shared by the command line and the worker."""
    return {
        "ok": True,
        "kernel": kernel_name,
        "results": [
            {
                "input": str(source),
                "mono": str(Path(r.mono_pdf).resolve()) if r.mono_pdf else None,
                "dual": str(Path(r.dual_pdf).resolve()) if r.dual_pdf else None,
            }
            for source, r in zip(files, results)
        ],
    }


class Cancelled(Exception):
    pass


class Worker:
    def __init__(self, out: TextIO, translate=None):
        self.out = out
        self.lock = threading.Lock()
        self.jobs: "queue.Queue[Optional[dict]]" = queue.Queue()
        self.waiting: dict[Any, dict] = {}  # id -> job, until it starts
        self.running: Optional[dict] = None
        self._translate = translate or translate_params

    def send(self, message: dict) -> None:
        line = json.dumps(message, ensure_ascii=False)
        with self.lock:
            self.out.write(line + "\n")
            self.out.flush()

    def handle(self, line: str) -> None:
        try:
            message = json.loads(line)
            if not isinstance(message, dict):
                raise ValueError("expected a JSON object")
        except ValueError as e:
            self.send({"id": None, "error": {"message": f"bad request: {e}"}})
            return
        request_id = message.get("id")
        method = message.get("method")
        params = message.get("params") or {}
        if method == "translate":
            job = {"id": request_id, "params": params, "cancel": threading.Event()}
            with self.lock:
                self.waiting[request_id] = job
            self.jobs.put(job)
        elif method == "cancel":
            self.cancel(params.get("id"))
            self.send({"id": request_id, "result": {"ok": True}})
        elif method == "ping":
            self.send({"id": request_id, "result": {"ok": True}})
        else:
            self.send(
                {"id": request_id, "error": {"message": f"unknown method {method!r}"}}
            )

    def cancel(self, target) -> None:
        with self.lock:
            job = self.waiting.pop(target, None)
            running = self.running
        if job is not None:
            job["cancel"].set()
            self.send(
                {"id": target, "error": {"message": "cancelled", "cancelled": True}}
            )
        elif running is not None and running["id"] == target:
            running["cancel"].set()

    def run_jobs(self) -> None:
        while True:
            job = self.jobs.get()
            if job is None:
                return
            with self.lock:
                if self.waiting.pop(job["id"], None) is None:
                    continue  # cancelled while waiting
                self.running = job
            try:
                result = self._translate(job["params"], job["cancel"])
                self.send({"id": job["id"], "result": result})
            except Exception as e:
                cancelled = job["cancel"].is_set()
                if not cancelled:
                    logger.exception("Translation failed")
                message = "cancelled" if cancelled else str(e) or type(e).__name__
                self.send(
                    {
                        "id": job["id"],
                        "error": {"message": message, "cancelled": cancelled},
                    }
                )
            finally:
                with self.lock:
                    self.running = None

    def stop(self) -> None:
        with self.lock:
            waiting = list(self.waiting)
            running = self.running
        for request_id in waiting:
            self.cancel(request_id)
        if running is not None:
            running["cancel"].set()
        self.jobs.put(None)


def translate_params(params: dict, cancel: threading.Event) -> dict:
    """Run one translation request from the protocol's params."""
    from pdf2zh.kernel import get_kernel
    from pdf2zh.kernel.protocol import TranslateRequest, parse_pages

    file = params.get("file")
    if not isinstance(file, str) or not file:
        raise ValueError("params.file is required")
    pages = params.get("pages")
    if isinstance(pages, list):
        pages = ",".join(str(p) for p in pages)
    kernel = get_kernel(params.get("kernel") or "auto")
    request = TranslateRequest(
        files=[file],
        output=params.get("output") or os.path.dirname(file),
        lang_in=params.get("lang_in") or "en",
        lang_out=params.get("lang_out") or "zh",
        service=params.get("service") or "google",
        pages=parse_pages(pages),
        thread=params.get("thread"),
        ignore_cache=bool(params.get("ignore_cache")),
    )
    results = kernel.translate(
        request, callback=lambda *args: None, cancellation_event=cancel
    )
    if cancel.is_set():
        raise Cancelled("cancelled")
    return result_payload(kernel.name, request.files, results)


def main(stdin: TextIO = None) -> int:
    from pdf2zh import __version__
    from pdf2zh.kernel import available_kernels, warm_up

    # The protocol keeps its own handle on the real stdout; everything else
    # written to stdout, including by native code, goes to stderr.
    out = os.fdopen(os.dup(sys.stdout.fileno()), "w", encoding="utf-8")
    sys.stdout.flush()
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    sys.stdout = sys.stderr

    worker = Worker(out)
    runner = threading.Thread(target=worker.run_jobs, name="pdf2zh-worker", daemon=True)
    runner.start()
    worker.send(
        {
            "ready": True,
            "protocol": PROTOCOL,
            "version": __version__,
            "kernels": available_kernels(),
        }
    )
    warm_up()
    stdin = stdin or sys.stdin
    for line in stdin:
        if line.strip():
            worker.handle(line)
    worker.stop()
    runner.join(timeout=30)
    return 0
