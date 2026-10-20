import importlib
import sys
import unittest


class TestCliVersion(unittest.TestCase):
    def setUp(self):
        for module_name in [
            "pdf2zh",
            "pdf2zh.pdf2zh",
            "pdf2zh.high_level",
            "pdf2zh.doclayout",
        ]:
            sys.modules.pop(module_name, None)

    def tearDown(self):
        self.setUp()

    def test_importing_package_does_not_eagerly_load_translation_pipeline(self):
        pkg = importlib.import_module("pdf2zh")

        self.assertEqual(pkg.__version__, "1.9.12")
        self.assertNotIn("pdf2zh.high_level", sys.modules)

    def test_version_flag_exits_before_loading_heavy_modules(self):
        cli = importlib.import_module("pdf2zh.pdf2zh")

        self.assertNotIn("pdf2zh.high_level", sys.modules)
        self.assertNotIn("pdf2zh.doclayout", sys.modules)

        with self.assertRaises(SystemExit) as exit_context:
            cli.main(["-v"])

        self.assertEqual(exit_context.exception.code, 0)
        self.assertNotIn("pdf2zh.high_level", sys.modules)
        self.assertNotIn("pdf2zh.doclayout", sys.modules)


if __name__ == "__main__":
    unittest.main()
