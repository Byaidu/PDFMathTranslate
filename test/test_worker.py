"""Tests for `pdf2zh --worker`."""

import io
import json
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pdf2zh.worker import Worker  # noqa: E402


class Lines(io.StringIO):
    """stdout stand-in that collects messages and lets tests wait for them."""

    def __init__(self):
        super().__init__()
        self.cond = threading.Condition()

    def write(self, text):
        with self.cond:
            n = super().write(text)
            self.cond.notify_all()
            return n

    def messages(self):
        return [json.loads(l) for l in self.getvalue().splitlines() if l]

    def wait(self, count, timeout=5):
        deadline = time.time() + timeout
        with self.cond:
            while len(self.messages()) < count:
                left = deadline - time.time()
                if left <= 0:
                    raise AssertionError(f"got {self.messages()}")
                self.cond.wait(left)
        return self.messages()


class TestWorker(unittest.TestCase):
    def start(self, translate):
        out = Lines()
        worker = Worker(out, translate=translate)
        thread = threading.Thread(target=worker.run_jobs, daemon=True)
        thread.start()
        self.addCleanup(lambda: (worker.stop(), thread.join(5)))
        return worker, out

    def test_requests_run_in_order(self):
        seen = []

        def translate(params, cancel):
            seen.append(params["file"])
            return {"ok": True, "file": params["file"]}

        worker, out = self.start(translate)
        for i in (1, 2):
            worker.handle(
                json.dumps(
                    {"id": i, "method": "translate", "params": {"file": f"{i}.pdf"}}
                )
            )
        messages = out.wait(2)
        self.assertEqual(seen, ["1.pdf", "2.pdf"])
        self.assertEqual([m["id"] for m in messages], [1, 2])
        self.assertEqual(messages[1]["result"]["file"], "2.pdf")

    def test_cancel_waiting_and_running(self):
        started = threading.Event()

        def translate(params, cancel):
            started.set()
            if not cancel.wait(5):
                raise AssertionError("not cancelled")
            raise RuntimeError("stopped")

        worker, out = self.start(translate)
        worker.handle(
            json.dumps({"id": "a", "method": "translate", "params": {"file": "a.pdf"}})
        )
        worker.handle(
            json.dumps({"id": "b", "method": "translate", "params": {"file": "b.pdf"}})
        )
        started.wait(5)
        worker.handle(json.dumps({"id": 1, "method": "cancel", "params": {"id": "b"}}))
        worker.handle(json.dumps({"id": 2, "method": "cancel", "params": {"id": "a"}}))
        by_id = {m["id"]: m for m in out.wait(4)}
        self.assertEqual(
            by_id["b"]["error"], {"message": "cancelled", "cancelled": True}
        )
        self.assertEqual(
            by_id["a"]["error"], {"message": "cancelled", "cancelled": True}
        )
        self.assertEqual(by_id[1]["result"], {"ok": True})

    def test_errors_are_reported(self):
        def translate(params, cancel):
            raise ValueError("params.file is required")

        worker, out = self.start(translate)
        worker.handle("not json")
        worker.handle(json.dumps({"id": 1, "method": "nope"}))
        worker.handle(json.dumps({"id": 2, "method": "translate", "params": {}}))
        messages = out.wait(3)
        self.assertIn("bad request", messages[0]["error"]["message"])
        self.assertIn("unknown method", messages[1]["error"]["message"])
        self.assertEqual(
            messages[2]["error"],
            {"message": "params.file is required", "cancelled": False},
        )


class TestWorkerProcess(unittest.TestCase):
    def test_ready_then_ping_then_exit_on_eof(self):
        proc = subprocess.run(
            [sys.executable, "-m", "pdf2zh.pdf2zh", "--worker"],
            input=json.dumps({"id": 7, "method": "ping"}) + "\n",
            capture_output=True,
            text=True,
            timeout=120,
            cwd=PROJECT_ROOT,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        lines = [json.loads(l) for l in proc.stdout.splitlines()]
        self.assertTrue(lines[0]["ready"])
        self.assertEqual(lines[0]["protocol"], 1)
        self.assertIn("legacy", lines[0]["kernels"])
        self.assertEqual(lines[1:], [{"id": 7, "result": {"ok": True}}])


if __name__ == "__main__":
    unittest.main()
