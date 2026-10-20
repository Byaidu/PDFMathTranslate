import unittest

import numpy as np
import pymupdf

from pdf2zh.doclayout import YoloResult
from pdf2zh.ocr import ocr_paragraphs, translate_ocr_page


def _pixels(page):
    pixmap = page.get_pixmap(alpha=False, annots=False)
    return np.frombuffer(pixmap.samples, np.uint8).reshape(
        pixmap.height, pixmap.width, pixmap.n
    )


class TestOCRLayout(unittest.TestCase):
    def test_interleaved_columns_group_by_detection_region(self):
        doc = pymupdf.open()
        page = doc.new_page(width=200, height=100)
        for text, point in (
            ("left one", (10, 20)),
            ("right one", (110, 20)),
            ("left two", (10, 40)),
            ("right two", (110, 40)),
        ):
            page.insert_text(point, text, fontsize=10, render_mode=3)
        detection = YoloResult(
            [
                np.array([0, 0, 95, 100, 0.9, 0]),
                np.array([100, 0, 200, 100, 0.9, 0]),
            ],
            ["text"],
        )

        paragraphs = ocr_paragraphs(page, detection)

        self.assertEqual(
            [paragraph[1] for paragraph in paragraphs],
            ["left one left two", "right one right two"],
        )
        self.assertLess(paragraphs[0][0].x1, paragraphs[1][0].x0)

    def test_fragmented_lines_rejoin_soft_hyphen_and_use_median_font(self):
        doc = pymupdf.open()
        page = doc.new_page(width=200, height=120)
        for text, point, size in (
            ("frag", (10, 20), 10),
            ("mented", (35, 20), 10),
            ("fertil-", (10, 40), 10),
            ("izer", (10, 60), 10),
            ("outlier", (10, 88), 28),
        ):
            page.insert_text(point, text, fontsize=size, render_mode=3)
        detection = YoloResult([np.array([0, 0, 200, 120, 0.9, 0])], ["text"])

        paragraphs = ocr_paragraphs(page, detection)

        self.assertEqual(len(paragraphs), 1)
        self.assertEqual(paragraphs[0][1], "frag mented fertilizer outlier")
        self.assertAlmostEqual(paragraphs[0][2], 10, delta=0.1)

    def test_translation_fits_escaped_text_and_preserves_figure_pixels(self):
        artwork = pymupdf.open()
        artwork_page = artwork.new_page(width=220, height=140)
        artwork_page.draw_rect(
            pymupdf.Rect(125, 70, 215, 135), color=None, fill=(1, 0, 0)
        )
        artwork_page.insert_text((10, 25), "body text", fontsize=18)
        artwork_page.insert_text((10, 100), "lower", fontsize=10)
        image = artwork_page.get_pixmap(alpha=False)

        doc = pymupdf.open()
        page = doc.new_page(width=220, height=140)
        page.insert_image(page.rect, pixmap=image)
        page.insert_text((10, 25), "body text", fontsize=18, render_mode=3)
        page.insert_text((10, 100), "lower", fontsize=10, render_mode=3)
        page.insert_text((135, 105), "figure secret", fontsize=10, render_mode=3)
        detection = YoloResult(
            [
                np.array([0, 0, 115, 65, 0.9, 1]),
                np.array([115, 0, 220, 140, 0.9, 0]),
            ],
            ["figure", "text"],
        )
        paragraphs = ocr_paragraphs(page, detection)
        body = next(
            paragraph for paragraph in paragraphs if paragraph[1] == "body text"
        )
        lower = next(paragraph for paragraph in paragraphs if paragraph[1] == "lower")
        before = _pixels(page)[70:135, 125:215].copy()

        class Translator:
            def __init__(self):
                self.calls = []

            def translate(self, text):
                self.calls.append(text)
                return "<tag>& " * (30 if text == "body text" else 1)

        translator = Translator()
        translate_ocr_page(page, detection, translator, pymupdf.Font("helv"), 1)

        self.assertEqual(translator.calls, ["body text", "lower"])
        self.assertTrue(np.array_equal(before, _pixels(page)[70:135, 125:215]))
        blocks = [
            block for block in page.get_text("dict")["blocks"] if block["type"] == 0
        ]
        body_block = next(
            block
            for block in blocks
            if "<tag>"
            in "".join(
                span["text"] for line in block["lines"] for span in line["spans"]
            )
        )
        body_text = "".join(
            span["text"] for line in body_block["lines"] for span in line["spans"]
        )
        self.assertIn("<tag>&", body_text)
        body_rect = pymupdf.Rect(body_block["bbox"])
        self.assertLessEqual(body_rect.x1, body[0].x1 + 0.5)
        self.assertLessEqual(body_rect.y1, lower[0].y0)
        self.assertLess(
            max(span["size"] for line in body_block["lines"] for span in line["spans"]),
            body[2],
        )


if __name__ == "__main__":
    unittest.main()
