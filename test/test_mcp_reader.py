"""Tests for the MCP Apps PDF reader."""

import asyncio
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import mcp  # noqa: F401
except ImportError:  # the reader is part of the mcp extra
    raise unittest.SkipTest("mcp is not installed")

import pymupdf

from pdf2zh.kernel.protocol import TranslateResult
from pdf2zh.mcp_reader import READER_URI, PageTranslator, Reader


def make_pdf(path: Path, pages: int = 3) -> Path:
    doc = pymupdf.open()
    for i in range(pages):
        page = doc.new_page(width=300, height=400)
        page.insert_text((50, 50), f"Page {i + 1}")
    doc.save(path)
    doc.close()
    return path


class FakeKernel:
    """Copies the input as the "translated" PDF and records each request."""

    def __init__(self):
        self.requests = []

    def translate(self, request, callback=None):
        self.requests.append(request)
        out = Path(request.output) / "mono.pdf"
        shutil.copy(request.files[0], out)
        return [TranslateResult(mono_pdf=str(out))]


class TestPageTranslator(unittest.TestCase):
    def test_pages_waiting_on_a_run_share_the_next_run(self):
        runs = []

        async def translate(doc_id, options, pages):
            runs.append(pages)
            await asyncio.sleep(0.05)
            return {p: Path(f"{doc_id}-{p}") for p in pages}

        async def main():
            t = PageTranslator(translate, batch=4)
            options = {"lang_out": "zh"}
            first = asyncio.create_task(t.page("doc", options, 1))
            await asyncio.sleep(0.01)  # page 1 is running
            rest = [asyncio.create_task(t.page("doc", options, p)) for p in (2, 3, 4)]
            return await asyncio.gather(first, *rest)

        results = asyncio.run(main())
        self.assertEqual(runs, [[1], [2, 3, 4]])
        self.assertEqual(results[2], Path("doc-3"))

    def test_options_are_not_mixed_in_one_run(self):
        runs = []

        async def translate(doc_id, options, pages):
            runs.append((options["lang_out"], pages))
            return {p: Path(str(p)) for p in pages}

        async def main():
            t = PageTranslator(translate)
            await asyncio.gather(
                t.page("doc", {"lang_out": "zh"}, 1),
                t.page("doc", {"lang_out": "ja"}, 2),
                t.page("doc", {"lang_out": "zh"}, 3),
            )

        asyncio.run(main())
        self.assertEqual(sorted(runs), [("ja", [2]), ("zh", [1, 3])])

    def test_cancelled_pages_are_dropped(self):
        runs = []

        async def translate(doc_id, options, pages):
            runs.append(pages)
            await asyncio.sleep(0.05)
            return {p: Path(str(p)) for p in pages}

        async def main():
            t = PageTranslator(translate)
            first = asyncio.create_task(t.page("doc", {}, 1))
            await asyncio.sleep(0.01)
            gone = asyncio.create_task(t.page("doc", {}, 2))
            kept = asyncio.create_task(t.page("doc", {}, 3))
            await asyncio.sleep(0.01)
            gone.cancel()
            await asyncio.gather(first, kept)

        asyncio.run(main())
        self.assertEqual(runs, [[1], [3]])


class TestReader(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.pdf = make_pdf(self.tmp / "paper.pdf")
        self.kernel = FakeKernel()
        self.reader = Reader(root=self.tmp / "cache", kernel_factory=lambda name: self.kernel)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_open(self):
        info = self.reader.open(str(self.pdf))
        self.assertEqual(info["title"], "paper.pdf")
        self.assertEqual(info["page_count"], 3)
        self.assertEqual(info["page_sizes"][0], [300.0, 400.0])
        self.assertTrue((self.tmp / "cache" / "documents" / f"{info['doc_id']}.pdf").is_file())

    def test_open_rejects_non_pdf(self):
        other = self.tmp / "notes.txt"
        other.write_text("hello")
        with self.assertRaises(ValueError):
            self.reader.open(str(other))
        with self.assertRaises(FileNotFoundError):
            self.reader.open(str(self.tmp / "missing.pdf"))

    def test_original_page_needs_no_translation(self):
        doc_id = self.reader.open(str(self.pdf))["doc_id"]
        data = asyncio.run(self.reader.image(doc_id, 2, 600, False, {}))
        self.assertTrue(data.startswith(b"\xff\xd8"))  # JPEG
        self.assertEqual(self.kernel.requests, [])

    def test_translated_pages_are_cached(self):
        doc_id = self.reader.open(str(self.pdf))["doc_id"]
        options = {"lang_in": "en", "lang_out": "zh", "service": "google", "kernel": "auto"}
        asyncio.run(self.reader.image(doc_id, 2, 600, True, options))
        self.assertEqual(len(self.kernel.requests), 1)
        self.assertEqual(self.kernel.requests[0].pages, [1])  # 0-based

        # A new reader over the same cache (a restarted server) reuses the page.
        again = Reader(root=self.tmp / "cache", kernel_factory=lambda name: self.kernel)
        data = asyncio.run(again.image(doc_id, 2, 600, True, options))
        self.assertTrue(data.startswith(b"\xff\xd8"))
        self.assertEqual(len(self.kernel.requests), 1)

    def test_later_runs_read_ahead(self):
        pdf = make_pdf(self.tmp / "long.pdf", pages=6)
        doc_id = self.reader.open(str(pdf))["doc_id"]
        options = {"lang_out": "zh"}

        async def main():
            await self.reader.translated_page(doc_id, 1, options)  # first run: just page 1
            await self.reader.translated_page(doc_id, 2, options)  # pages 2-5
            await self.reader.translated_page(doc_id, 4, options)  # cached

        asyncio.run(main())
        self.assertEqual([r.pages for r in self.kernel.requests], [[0], [1, 2, 3, 4]])
        self.assertTrue(all(r.no_dual for r in self.kernel.requests))

    def test_pages_of_a_running_batch_wait_for_it(self):
        pdf = make_pdf(self.tmp / "long.pdf", pages=6)
        doc_id = self.reader.open(str(pdf))["doc_id"]
        options = {"lang_out": "zh"}

        async def main():
            await self.reader.translated_page(doc_id, 1, options)
            batch = asyncio.create_task(self.reader.translated_page(doc_id, 2, options))
            await asyncio.sleep(0.05)  # pages 2-5 are running
            await asyncio.gather(batch, self.reader.translated_page(doc_id, 3, options))

        slow = self.kernel.translate

        def translate(request, callback=None):
            import time

            time.sleep(0.2)
            return slow(request, callback)

        self.kernel.translate = translate
        asyncio.run(main())
        self.assertEqual(len(self.kernel.requests), 2)

    def test_open_prefetches_the_first_page(self):
        async def main():
            info = self.reader.open(str(self.pdf))
            self.reader.prefetch(info["doc_id"], {"lang_out": "zh"})
            await asyncio.sleep(0.3)

        asyncio.run(main())
        self.assertEqual([r.pages for r in self.kernel.requests], [[0]])

    def test_page_out_of_range(self):
        doc_id = self.reader.open(str(self.pdf))["doc_id"]
        with self.assertRaises(ValueError):
            asyncio.run(self.reader.image(doc_id, 9, 600, False, {}))

    def test_unknown_document(self):
        with self.assertRaises(ValueError):
            asyncio.run(self.reader.image("0" * 64, 1, 600, False, {}))


class TestRegistration(unittest.TestCase):
    def test_tools_and_resource(self):
        from pdf2zh.mcp_server import create_mcp_app

        app = create_mcp_app()
        tools = {t.name: t for t in asyncio.run(app.list_tools())}
        self.assertEqual(tools["open_pdf_reader"].meta["ui"]["resourceUri"], READER_URI)
        self.assertEqual(tools["get_pdf_page"].meta["ui"]["visibility"], ["app"])

        resources = {str(r.uri): r for r in asyncio.run(app.list_resources())}
        resource = resources[READER_URI]
        self.assertEqual(resource.mime_type if hasattr(resource, "mime_type") else resource.mimeType,
                         "text/html;profile=mcp-app")
        self.assertIn("https://unpkg.com", resource.meta["ui"]["csp"]["resourceDomains"])


if __name__ == "__main__":
    unittest.main()
