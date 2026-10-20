import asyncio
import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

import numpy as np
import pymupdf

_CACHE_HOME = tempfile.mkdtemp()


def _expanduser(path):
    return _CACHE_HOME if path == "~" else path


with patch("os.path.expanduser", side_effect=_expanduser):
    import pdf2zh.high_level as high_level
    from pdf2zh.high_level import _ocr_pages
from pdf2zh.doclayout import YoloResult


def _source_pdf():
    doc = pymupdf.open()

    def add_image(page):
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, (0, 0, 24, 16), False)
        pixmap.clear_with(255)
        page.insert_image(page.rect, pixmap=pixmap)

    target = doc.new_page(width=120, height=80)
    add_image(target)
    target.insert_link(
        {
            "kind": pymupdf.LINK_URI,
            "from": pymupdf.Rect(5, 5, 25, 15),
            "uri": "https://example.com",
        }
    )

    unselected = doc.new_page(width=120, height=80)
    add_image(unselected)

    native = doc.new_page(width=120, height=80)
    native.insert_text((10, 20), "native text")

    doc.new_page(width=120, height=80)

    existing = doc.new_page(width=120, height=80)
    add_image(existing)
    existing.insert_text((10, 20), "existing OCR")
    return doc.tobytes()


def _recognized_pdf():
    doc = pymupdf.open()
    page = doc.new_page(width=120, height=80)
    page.insert_text((10, 20), "recognized text")
    return doc.tobytes()


def _scan_streams():
    def add_text(page, render_mode=0):
        page.insert_text(
            (10, 25), "body", fontname="helv", fontsize=6, render_mode=render_mode
        )
        page.insert_text(
            (30, 25), " words", fontname="helv", fontsize=18, render_mode=render_mode
        )
        page.insert_text(
            (10, 65), "protected", fontname="helv", fontsize=18, render_mode=render_mode
        )

    with pymupdf.open() as artwork:
        add_text(artwork.new_page(width=120, height=80))
        image = artwork[0].get_pixmap(alpha=False)
        with pymupdf.open() as scan:
            scan_page = scan.new_page(width=120, height=80)
            scan_page.insert_image(scan_page.rect, pixmap=image)
            source = scan.tobytes()
            with pymupdf.open() as recognized:
                recognized_page = recognized.new_page(width=120, height=80)
                recognized_page.insert_image(recognized_page.rect, pixmap=image)
                add_text(recognized_page, render_mode=3)
                return source, recognized.tobytes()


def _pixels(page):
    pixmap = page.get_pixmap(alpha=False, annots=False)
    return np.frombuffer(pixmap.samples, np.uint8).reshape(
        pixmap.height, pixmap.width, pixmap.n
    )


class TestOCRPages(unittest.TestCase):
    def test_selection_skips_native_blank_and_existing_layers(self):
        source = _source_pdf()
        recognized = _recognized_pdf()

        with pymupdf.open(stream=source) as doc:
            page_xrefs = [page.xref for page in doc]
            target_rect = doc[0].rect
            with patch.object(
                high_level, "_ocr_tessdata", return_value="/tmp/tessdata"
            ) as tessdata:
                with patch.object(
                    pymupdf.Pixmap, "pdfocr_tobytes", return_value=recognized
                ) as ocr:
                    result = _ocr_pages(doc, [0, 2, 3, 4], "en", None)

            self.assertEqual(result, {0})
            tessdata.assert_called_once_with("eng")
            ocr.assert_called_once_with(language="eng", tessdata="/tmp/tessdata")
            self.assertEqual([page.xref for page in doc], page_xrefs)
            self.assertEqual(doc[0].rect, target_rect)
            self.assertEqual(doc[0].get_text().strip(), "recognized text")
            self.assertEqual(doc[0].get_links()[0]["uri"], "https://example.com")
            self.assertEqual(doc[1].get_text().strip(), "")
            self.assertEqual(doc[2].get_text().strip(), "native text")
            self.assertEqual(doc[3].get_text().strip(), "")
            self.assertEqual(doc[4].get_text().strip(), "existing OCR")

    def test_ocr_failure_has_actionable_error(self):
        with pymupdf.open(stream=_source_pdf()) as doc:
            with patch.object(
                high_level, "_ocr_tessdata", return_value="/tmp/tessdata"
            ):
                with patch.object(
                    pymupdf.Pixmap,
                    "pdfocr_tobytes",
                    side_effect=RuntimeError("tesseract unavailable"),
                ):
                    with self.assertRaisesRegex(
                        RuntimeError, "OCR failed on page 1.*TESSDATA_PREFIX"
                    ):
                        _ocr_pages(doc, [0], "en", None)

    def test_cancellation_stops_before_ocr(self):
        event = asyncio.Event()
        event.set()
        with pymupdf.open(stream=_source_pdf()) as doc:
            with patch.object(high_level, "_ocr_tessdata") as tessdata:
                with patch.object(pymupdf.Pixmap, "pdfocr_tobytes") as ocr:
                    with self.assertRaises(asyncio.CancelledError):
                        _ocr_pages(doc, [0], "en", event)
                    tessdata.assert_not_called()
                    ocr.assert_not_called()

    def test_no_candidate_does_not_resolve_tessdata(self):
        with pymupdf.open(stream=_source_pdf()) as doc:
            with patch.object(high_level, "_ocr_tessdata") as tessdata:
                with patch.object(pymupdf.Pixmap, "pdfocr_tobytes") as ocr:
                    self.assertEqual(_ocr_pages(doc, [2, 3, 4], "en", None), set())
                    tessdata.assert_not_called()
                    ocr.assert_not_called()

    def test_tessdata_explicit_override_skips_download(self):
        with patch.dict(os.environ, {"TESSDATA_PREFIX": "/manual/tessdata"}):
            with patch.dict(sys.modules, {"pooch": None}):
                self.assertEqual(
                    high_level._ocr_tessdata("eng+deu"), "/manual/tessdata"
                )

    def test_tessdata_rejects_invalid_language(self):
        with patch.dict(os.environ, {"TESSDATA_PREFIX": ""}):
            for language in ("../eng", "eng/foo", "eng+"):
                with self.assertRaisesRegex(ValueError, "Invalid OCR language"):
                    high_level._ocr_tessdata(language)

    def test_tessdata_missing_optional_dependency_is_actionable(self):
        with tempfile.TemporaryDirectory() as home:
            with patch.dict(os.environ, {"TESSDATA_PREFIX": ""}):
                with patch.object(high_level.Path, "home", return_value=Path(home)):
                    with patch.dict(sys.modules, {"pooch": None}):
                        with self.assertRaisesRegex(RuntimeError, r"pdf2zh\[ocr\]"):
                            high_level._ocr_tessdata("eng")

    def test_tessdata_downloads_each_language_and_reuses_cache(self):
        try:
            import pooch
        except ImportError:
            self.skipTest("pooch optional dependency is unavailable")

        with tempfile.TemporaryDirectory() as home:
            downloads = []

            def download(url, output_file, _pooch, check_only=False):
                downloads.append(url)
                Path(output_file).write_bytes(b"traineddata")

            downloader = Mock(side_effect=download)
            with patch.dict(os.environ, {"TESSDATA_PREFIX": ""}):
                with patch.object(high_level.Path, "home", return_value=Path(home)):
                    with patch.object(
                        pooch, "HTTPDownloader", return_value=downloader
                    ) as make_downloader:
                        downloader.side_effect = high_level.requests.ConnectionError(
                            "offline"
                        )
                        with self.assertRaisesRegex(
                            RuntimeError, "Could not download OCR data"
                        ):
                            high_level._ocr_tessdata("eng")
                        self.assertFalse(list(Path(home).rglob("*.traineddata")))
                        downloader.reset_mock()
                        downloader.side_effect = download
                        cache = high_level._ocr_tessdata("eng+deu")
                        self.assertEqual(
                            cache,
                            str(Path(home) / ".cache/pdf2zh/tessdata/4.1.0"),
                        )
                        self.assertEqual(cache, high_level._ocr_tessdata("eng+deu"))

            self.assertEqual(
                downloads,
                [
                    "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/4.1.0/eng.traineddata",
                    "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/4.1.0/deu.traineddata",
                ],
            )
            self.assertEqual(downloader.call_count, 2)
            self.assertEqual(make_downloader.call_args.kwargs, {"timeout": 60})

    def test_translate_stream_ocr_masks_body_and_preserves_source(self):
        source, recognized = _scan_streams()
        layout = YoloResult(
            [
                np.array([0, 42, 120, 80, 0.95, 0]),
                np.array([0, 0, 120, 42, 0.90, 1]),
            ],
            ["figure", "text"],
        )
        model = Mock()
        model.predict.return_value = [layout]
        calls = []

        def translate(text):
            calls.append(text)
            return "X"

        with (
            patch.object(high_level, "download_remote_fonts", return_value=None),
            patch.object(high_level, "NOTO_NAME", "helv"),
            patch.object(high_level, "_ocr_tessdata", return_value="/tmp/tessdata"),
            patch.object(pymupdf.Pixmap, "pdfocr_tobytes", return_value=recognized),
            patch(
                "pdf2zh.translator.GoogleTranslator.translate", side_effect=translate
            ),
        ):
            mono, dual = high_level.translate_stream(
                source,
                lang_in="en",
                lang_out="en",
                service="google",
                thread=1,
                model=model,
                skip_subset_fonts=True,
            )

        self.assertEqual(len(calls), 1)
        self.assertIn("body", calls[0])
        self.assertIn("words", calls[0])
        self.assertNotIn("{v", calls[0])
        self.assertNotIn("protected", calls[0])
        with (
            pymupdf.open(stream=source) as source_doc,
            pymupdf.open(stream=mono) as mono_doc,
            pymupdf.open(stream=dual) as dual_doc,
        ):
            self.assertEqual(mono_doc[0].get_text().strip(), "X")
            self.assertNotIn("protected", mono_doc[0].get_text())
            source_pixels = _pixels(source_doc[0])
            mono_pixels = _pixels(mono_doc[0])
            self.assertTrue(np.array_equal(source_pixels, _pixels(dual_doc[0])))
            self.assertTrue(
                np.array_equal(source_pixels[45:72, 10:85], mono_pixels[45:72, 10:85])
            )
            source_crop = source_pixels[5:32, 35:80]
            mono_crop = mono_pixels[5:32, 35:80]
            self.assertGreater(np.count_nonzero(source_crop[:, :, :3] < 128), 0)
            self.assertEqual(np.count_nonzero(mono_crop[:, :, :3] < 200), 0)
