"""Code shapes that downstream projects read from pdf2zh's source.

PDFMathReader (server/kernels/python/kernel-services.py) lists the fast
kernel's translation services by parsing TranslateConverter.__init__ for a
`for ... in [SomeTranslator, ...]` loop over a literal list. Replacing that
loop leaves PDFMathReader with no services.
"""

import ast
import inspect
import sys
import textwrap
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def converter_translator_names():
    """PDFMathReader's _fast_converter_names(), applied to this checkout."""
    from pdf2zh import converter

    source = textwrap.dedent(inspect.getsource(converter.TranslateConverter.__init__))
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.For) or not isinstance(
            node.iter, (ast.List, ast.Tuple)
        ):
            continue
        names = [item.id for item in node.iter.elts if isinstance(item, ast.Name)]
        if names:
            return names
    return []


class TestPDFMathReaderServiceDiscovery(unittest.TestCase):
    def test_converter_translator_list(self):
        from pdf2zh import converter, translator

        names = converter_translator_names()
        self.assertTrue(names, "TranslateConverter.__init__ lost its literal list")
        classes = [getattr(converter, name) for name in names]
        for cls in classes:
            self.assertEqual(cls.__module__, translator.__name__)
        # Every service create_translator() knows is listed for PDFMathReader.
        self.assertEqual(
            {cls.name for cls in classes},
            {cls.name for cls in translator.TRANSLATORS},
        )


if __name__ == "__main__":
    unittest.main()
