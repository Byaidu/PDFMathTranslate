import unittest
from unittest.mock import MagicMock
from unittest.mock import Mock
from unittest.mock import patch

from pdf2zh.converter import PDFConverterEx
from pdf2zh.converter import TranslateConverter
from pdfminer.layout import LTChar
from pdfminer.layout import LTLine
from pdfminer.layout import LTPage
from pdfminer.pdfinterp import PDFResourceManager


class TestPDFConverterEx(unittest.TestCase):
    def setUp(self):
        self.rsrcmgr = PDFResourceManager()
        self.converter = PDFConverterEx(self.rsrcmgr)

    def test_begin_page(self):
        mock_page = Mock()
        mock_page.pageno = 1
        mock_page.cropbox = (0, 0, 100, 200)
        mock_ctm = [1, 0, 0, 1, 0, 0]
        self.converter.begin_page(mock_page, mock_ctm)
        self.assertIsNotNone(self.converter.cur_item)
        self.assertEqual(self.converter.cur_item.pageid, 1)

    def test_render_char(self):
        mock_matrix = (1, 2, 3, 4, 5, 6)
        mock_font = Mock()
        mock_font.to_unichr.return_value = "A"
        mock_font.char_width.return_value = 10
        mock_font.char_disp.return_value = (0, 0)
        graphic_state = Mock()
        self.converter.cur_item = Mock()
        result = self.converter.render_char(
            mock_matrix,
            mock_font,
            fontsize=12,
            scaling=1.0,
            rise=0,
            cid=65,
            ncs=None,
            graphicstate=graphic_state,
        )
        self.assertEqual(result, 120.0)  # Expected text width


class TestTranslateConverter(unittest.TestCase):
    def setUp(self):
        self.rsrcmgr = PDFResourceManager()
        self.layout = {1: Mock()}
        self.translator_class = Mock()
        self.converter = TranslateConverter(
            self.rsrcmgr,
            layout=self.layout,
            lang_in="en",
            lang_out="zh",
            service="google",
        )

    def test_translator_initialization(self):
        self.assertIsNotNone(self.converter.translator)
        self.assertEqual(self.converter.translator.lang_in, "en")
        self.assertEqual(self.converter.translator.lang_out, "zh-CN")

    @patch("pdf2zh.converter.TranslateConverter.receive_layout")
    def test_receive_layout(self, mock_receive_layout):
        mock_page = LTPage(1, (0, 0, 100, 200))
        mock_font = Mock()
        mock_font.fontname.return_value = "mock_font"
        mock_page.add(
            LTChar(
                matrix=(1, 2, 3, 4, 5, 6),
                font=mock_font,
                fontsize=12,
                scaling=1.0,
                rise=0,
                text="A",
                textwidth=10,
                textdisp=(1.0, 1.0),
                ncs=Mock(),
                graphicstate=Mock(),
            )
        )
        self.converter.receive_layout(mock_page)
        mock_receive_layout.assert_called_once_with(mock_page)

    def test_receive_layout_with_complex_formula(self):
        ltpage = LTPage(1, (0, 0, 500, 500))
        ltchar = Mock()
        ltchar.fontname.return_value = "mock_font"
        ltline = LTLine(0.1, (0, 0), (10, 20))
        ltpage.add(ltchar)
        ltpage.add(ltline)
        mock_layout = MagicMock()
        mock_layout.shape = (100, 100)
        mock_layout.__getitem__.return_value = -1
        self.converter.layout = [None, mock_layout]
        self.converter.thread = 1
        result = self.converter.receive_layout(ltpage)
        self.assertIsNotNone(result)

    def test_invalid_translation_service(self):
        with self.assertRaises(ValueError):
            TranslateConverter(
                self.rsrcmgr,
                layout=self.layout,
                lang_in="en",
                lang_out="zh",
                service="InvalidService",
            )


if __name__ == "__main__":
    unittest.main()
