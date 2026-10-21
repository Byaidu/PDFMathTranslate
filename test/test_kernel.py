"""Tests for the kernel abstraction layer."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure the project root is on the path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestKernelProtocol(unittest.TestCase):
    """Test TranslateRequest and TranslateResult dataclasses."""

    def test_translate_request_defaults(self):
        from pdf2zh.kernel.protocol import TranslateRequest

        req = TranslateRequest(files=["test.pdf"])
        self.assertEqual(req.files, ["test.pdf"])
        self.assertEqual(req.lang_in, "en")
        self.assertEqual(req.lang_out, "zh")
        self.assertEqual(req.service, "google")
        self.assertEqual(req.thread, 4)
        self.assertIsNone(req.pages)
        self.assertFalse(req.debug)

    def test_translate_result_defaults(self):
        from pdf2zh.kernel.protocol import TranslateResult

        result = TranslateResult()
        self.assertIsNone(result.mono_pdf)
        self.assertIsNone(result.dual_pdf)
        self.assertEqual(result.time_cost, 0.0)

    def test_translate_result_with_paths(self):
        from pdf2zh.kernel.protocol import TranslateResult

        result = TranslateResult(
            mono_pdf=Path("/tmp/mono.pdf"),
            dual_pdf=Path("/tmp/dual.pdf"),
            time_cost=1.5,
        )
        self.assertEqual(result.mono_pdf, Path("/tmp/mono.pdf"))
        self.assertEqual(result.time_cost, 1.5)


class TestKernelRegistry(unittest.TestCase):
    """Test KernelRegistry singleton."""

    def setUp(self):
        from pdf2zh.kernel.registry import KernelRegistry

        self._registry = KernelRegistry
        self._orig_kernels = dict(KernelRegistry._kernels)
        self._orig_active = KernelRegistry._active

    def tearDown(self):
        self._registry._kernels = self._orig_kernels
        self._registry._active = self._orig_active

    def test_register_and_get(self):
        from pdf2zh.kernel.registry import KernelRegistry

        mock_kernel = MagicMock()
        mock_kernel.name = "test_kernel"
        mock_kernel.is_available.return_value = True

        KernelRegistry.register(mock_kernel)
        self.assertIs(KernelRegistry.get("test_kernel"), mock_kernel)

    def test_get_nonexistent_raises(self):
        from pdf2zh.kernel.registry import KernelRegistry

        with self.assertRaises(KeyError):
            KernelRegistry.get("nonexistent_kernel_xyz")

    def test_switch_and_active_name(self):
        from pdf2zh.kernel.registry import KernelRegistry

        mock_kernel = MagicMock()
        mock_kernel.name = "switchable"
        mock_kernel.is_available.return_value = True

        KernelRegistry.register(mock_kernel)
        KernelRegistry.switch("switchable")
        self.assertEqual(KernelRegistry.active_name(), "switchable")

    def test_switch_unavailable_raises(self):
        from pdf2zh.kernel.registry import KernelRegistry

        mock_kernel = MagicMock()
        mock_kernel.name = "unavailable"
        mock_kernel.is_available.return_value = False

        KernelRegistry.register(mock_kernel)
        with self.assertRaises(RuntimeError):
            KernelRegistry.switch("unavailable")

    def test_available_filters_correctly(self):
        from pdf2zh.kernel.registry import KernelRegistry

        k1 = MagicMock()
        k1.name = "avail1"
        k1.is_available.return_value = True

        k2 = MagicMock()
        k2.name = "unavail1"
        k2.is_available.return_value = False

        KernelRegistry.register(k1)
        KernelRegistry.register(k2)

        available = KernelRegistry.available()
        self.assertIn("avail1", available)
        self.assertNotIn("unavail1", available)

    def test_aliases_resolve_to_kernel_names(self):
        from pdf2zh.kernel.registry import KernelRegistry

        self.assertEqual(KernelRegistry.resolve("fast"), "legacy")
        self.assertEqual(KernelRegistry.resolve("precise"), "babeldoc")
        self.assertEqual(KernelRegistry.resolve("legacy"), "legacy")

    def test_auto_prefers_legacy_then_babeldoc(self):
        from pdf2zh.kernel.registry import KernelRegistry

        babeldoc, legacy = MagicMock(), MagicMock()
        babeldoc.name, legacy.name = "babeldoc", "legacy"
        KernelRegistry._kernels = {"babeldoc": babeldoc, "legacy": legacy}

        babeldoc.is_available.return_value = True
        legacy.is_available.return_value = True
        self.assertEqual(KernelRegistry.resolve("auto"), "legacy")

        legacy.is_available.return_value = False
        self.assertEqual(KernelRegistry.resolve("auto"), "babeldoc")

        babeldoc.is_available.return_value = False
        with self.assertRaises(RuntimeError):
            KernelRegistry.resolve("auto")

    def test_switch_unavailable_names_install_command(self):
        from pdf2zh.kernel.registry import KernelRegistry

        babeldoc = MagicMock()
        babeldoc.name = "babeldoc"
        babeldoc.is_available.return_value = False
        KernelRegistry._kernels = {"babeldoc": babeldoc}
        with self.assertRaisesRegex(RuntimeError, r"Python 3\.11 to 3\.13"):
            KernelRegistry.switch("precise")

    def test_babeldoc_unavailable_on_python_314(self):
        from pdf2zh.kernel.babeldoc_kernel import BabelDOCKernel

        with patch("importlib.util.find_spec", return_value=object()):
            with patch("sys.version_info", (3, 14, 0)):
                self.assertFalse(BabelDOCKernel().is_available())
            with patch("sys.version_info", (3, 13, 5)):
                self.assertTrue(BabelDOCKernel().is_available())


class TestLegacyKernelVersion(unittest.TestCase):

    def test_name(self):
        from pdf2zh.kernel.legacy import LegacyKernel

        k = LegacyKernel()
        self.assertEqual(k.name, "legacy")

    def test_version(self):
        from pdf2zh import __version__
        from pdf2zh.kernel.legacy import LegacyKernel

        k = LegacyKernel()
        self.assertEqual(k.version, __version__)

    def test_is_available(self):
        from pdf2zh.kernel.legacy import LegacyKernel

        k = LegacyKernel()
        self.assertTrue(k.is_available())


class TestKernelInit(unittest.TestCase):

    def test_both_kernels_registered(self):
        from pdf2zh.kernel import KernelRegistry

        self.assertEqual(KernelRegistry.get("legacy").name, "legacy")
        self.assertEqual(KernelRegistry.get("babeldoc").name, "babeldoc")

    def test_old_mode_names_still_work(self):
        from pdf2zh.kernel import KernelRegistry

        self.assertEqual(KernelRegistry.get("fast").name, "legacy")
        self.assertEqual(KernelRegistry.get("precise").name, "babeldoc")

    def test_package_exports_unified_api(self):
        import pdf2zh

        self.assertIn("legacy", pdf2zh.available_kernels())
        self.assertEqual(pdf2zh.get_kernel("auto").name, "legacy")
        request = pdf2zh.TranslateRequest(files=["a.pdf"])
        self.assertEqual(request.files, ["a.pdf"])


class TestLegacyKernelTranslation(unittest.TestCase):
    """Test LegacyKernel.translate() with mocked high_level.translate()."""

    @patch("pdf2zh.high_level.translate")
    @patch("pdf2zh.doclayout.OnnxModel")
    @patch("pdf2zh.doclayout.ModelInstance")
    def test_translate_single_file(self, mock_model_inst, mock_onnx, mock_translate):
        mock_model_inst.value = MagicMock()
        mock_translate.return_value = [("/tmp/mono.pdf", "/tmp/dual.pdf")]

        from pdf2zh.kernel.legacy import LegacyKernel
        from pdf2zh.kernel.protocol import TranslateRequest

        k = LegacyKernel()
        req = TranslateRequest(files=["test.pdf"], service="google")
        results = k.translate(req)

        mock_translate.assert_called_once()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].mono_pdf, Path("/tmp/mono.pdf"))
        self.assertEqual(results[0].dual_pdf, Path("/tmp/dual.pdf"))

    @patch("pdf2zh.high_level.translate")
    @patch("pdf2zh.doclayout.OnnxModel")
    @patch("pdf2zh.doclayout.ModelInstance")
    def test_translate_passes_all_params(
        self, mock_model_inst, mock_onnx, mock_translate
    ):
        mock_model_inst.value = MagicMock()
        mock_translate.return_value = []

        from pdf2zh.kernel.legacy import LegacyKernel
        from pdf2zh.kernel.protocol import TranslateRequest

        k = LegacyKernel()
        req = TranslateRequest(
            files=["test.pdf"],
            lang_in="ja",
            lang_out="en",
            service="openai",
            thread=8,
            vfont="Arial",
            vchar="[a-z]",
            envs={"OPENAI_API_KEY": "sk-test"},
            ignore_cache=True,
            compatible=True,
        )
        k.translate(req)

        call_kwargs = mock_translate.call_args[1]
        self.assertEqual(call_kwargs["lang_in"], "ja")
        self.assertEqual(call_kwargs["lang_out"], "en")
        self.assertEqual(call_kwargs["service"], "openai")
        self.assertEqual(call_kwargs["thread"], 8)
        self.assertTrue(call_kwargs["ignore_cache"])
        self.assertTrue(call_kwargs["compatible"])

    @patch("pdf2zh.high_level.translate")
    @patch("pdf2zh.doclayout.OnnxModel")
    @patch("pdf2zh.doclayout.ModelInstance")
    def test_translate_with_prompt_wraps_template(
        self, mock_model_inst, mock_onnx, mock_translate
    ):
        mock_model_inst.value = MagicMock()
        mock_translate.return_value = []

        from pdf2zh.kernel.legacy import LegacyKernel
        from pdf2zh.kernel.protocol import TranslateRequest

        k = LegacyKernel()
        req = TranslateRequest(files=["test.pdf"], prompt="Be formal")
        k.translate(req)

        call_kwargs = mock_translate.call_args[1]
        from string import Template

        self.assertIsInstance(call_kwargs["prompt"], Template)
        self.assertEqual(call_kwargs["prompt"].template, "Be formal")


# BabelDOC 0.6 fails to import on Python 3.14; its kernel is unavailable there.
BABELDOC_RUNS = sys.version_info < (3, 14)


@unittest.skipUnless(BABELDOC_RUNS, "the BabelDOC kernel needs Python < 3.14")
class TestBabelDOCKernel(unittest.TestCase):
    """Test the in-process BabelDOC kernel with BabelDOC's pipeline mocked."""

    def test_pages_to_babeldoc(self):
        from pdf2zh.kernel.babeldoc_kernel import pages_to_babeldoc

        self.assertIsNone(pages_to_babeldoc(None))
        self.assertIsNone(pages_to_babeldoc([]))
        self.assertEqual(pages_to_babeldoc([0, 2, 3]), "1,3,4")

    def test_version_is_babeldoc_version(self):
        from importlib.metadata import version
        from pdf2zh.kernel.babeldoc_kernel import BabelDOCKernel

        self.assertEqual(BabelDOCKernel().version, version("babeldoc"))

    LAYOUT_MODEL = object()

    def _run(self, events, **request_kwargs):
        # patch() can only replace attributes of modules that are imported.
        import babeldoc.format.pdf.high_level  # noqa: F401
        import babeldoc.format.pdf.translation_config  # noqa: F401
        from pdf2zh.kernel.babeldoc_kernel import BabelDOCKernel
        from pdf2zh.kernel.protocol import TranslateRequest

        async def fake_translate(config):
            for event in events:
                yield event

        config_cls = MagicMock(name="TranslationConfig")
        callback = MagicMock()
        with (
            patch("babeldoc.format.pdf.high_level.init"),
            patch("babeldoc.format.pdf.high_level.async_translate", fake_translate),
            patch(
                "babeldoc.format.pdf.translation_config.TranslationConfig", config_cls
            ),
            patch("pdf2zh.translator.create_translator") as create,
            patch(
                "pdf2zh.kernel.babeldoc_kernel.layout_model",
                return_value=self.LAYOUT_MODEL,
            ),
        ):
            create.return_value = MagicMock(
                name="google", lang_in="en", lang_out="zh", model=None
            )
            create.return_value.name = "google"
            request = TranslateRequest(files=["paper.pdf"], **request_kwargs)
            results = BabelDOCKernel().translate(request, callback=callback)
        return results, config_cls, callback, create

    def test_translate_maps_request_and_collects_result(self):
        finish = MagicMock(
            mono_pdf_path="/out/a.mono.pdf",
            dual_pdf_path="/out/a.dual.pdf",
            total_seconds=2.0,
        )
        progress = {
            "type": "progress_update",
            "stage": "Translate",
            "overall_progress": 50.0,
        }
        results, config_cls, callback, create = self._run(
            [progress, {"type": "finish", "translate_result": finish}],
            pages=[0, 1],
            output="/out",
            thread=8,
            service="deepl",
            lang_out="ja",
        )

        create.assert_called_once()
        self.assertEqual(create.call_args[0][:3], ("deepl", "en", "ja"))
        kwargs = config_cls.call_args.kwargs
        self.assertEqual(kwargs["input_file"], "paper.pdf")
        self.assertEqual(kwargs["pages"], "1,2")
        self.assertEqual(kwargs["output_dir"], "/out")
        self.assertEqual(kwargs["qps"], 8)
        self.assertIs(kwargs["doc_layout_model"], self.LAYOUT_MODEL)
        self.assertFalse(kwargs["no_dual"])
        callback.assert_any_call(progress)
        self.assertEqual(results[0].mono_pdf, Path("/out/a.mono.pdf"))
        self.assertEqual(results[0].dual_pdf, Path("/out/a.dual.pdf"))
        self.assertEqual(results[0].time_cost, 2.0)

    def test_error_event_raises(self):
        with self.assertRaisesRegex(RuntimeError, "boom"):
            self._run([{"type": "error", "error": "boom"}])


@unittest.skipUnless(BABELDOC_RUNS, "the BabelDOC kernel needs Python < 3.14")
class TestBabelDOCTranslatorAdapter(unittest.TestCase):
    """BabelDOC uses do_llm_translate(None) to detect LLM support."""

    def _inner(self, name="google", client=None):
        inner = MagicMock()
        inner.name = name
        inner.lang_in, inner.lang_out, inner.model = "en", "zh", "m"
        inner.client = client
        inner.options = {"temperature": 0}
        inner.think_filter_regex = None
        inner.do_translate.return_value = "translated"
        return inner

    def test_non_llm_service_falls_back_to_do_translate(self):
        from pdf2zh.kernel.babeldoc_kernel import create_babeldoc_translator

        adapter = create_babeldoc_translator(self._inner(), ignore_cache=True)
        with self.assertRaises(NotImplementedError):
            adapter.do_llm_translate(None)
        self.assertEqual(adapter.translate("hello"), "translated")
        self.assertTrue(adapter.name.startswith("pdf2zh-google"))
        self.assertLessEqual(len(adapter.name), 20)

    def test_openai_compatible_service_supports_llm(self):
        import openai
        from pdf2zh.kernel.babeldoc_kernel import create_babeldoc_translator

        client = MagicMock(spec=openai.OpenAI)
        client.chat = MagicMock()
        client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content="  译文  "))
        ]
        adapter = create_babeldoc_translator(
            self._inner("openai", client), ignore_cache=True
        )
        self.assertIsNone(adapter.do_llm_translate(None))
        self.assertEqual(adapter.llm_translate("prompt"), "译文")
        sent = client.chat.completions.create.call_args.kwargs
        self.assertEqual(sent["model"], "m")
        self.assertEqual(sent["messages"], [{"role": "user", "content": "prompt"}])

    def test_mt_model_with_openai_client_is_not_llm(self):
        import openai
        from pdf2zh.kernel.babeldoc_kernel import create_babeldoc_translator

        adapter = create_babeldoc_translator(
            self._inner("qwen-mt", MagicMock(spec=openai.OpenAI)), ignore_cache=True
        )
        with self.assertRaises(NotImplementedError):
            adapter.do_llm_translate(None)


class TestCLIKernelPipeline(unittest.TestCase):
    """Test that CLI args correctly flow through the kernel layer."""

    def _main(self, argv):
        mock_kernel = MagicMock()
        mock_kernel.translate.return_value = []
        with (
            patch("pdf2zh.kernel.registry.KernelRegistry.switch") as switch,
            patch(
                "pdf2zh.kernel.registry.KernelRegistry.get", return_value=mock_kernel
            ),
            patch("pdf2zh.doclayout.set_backend"),
            patch("pdf2zh.doclayout.OnnxModel"),
            patch("pdf2zh.doclayout.ModelInstance"),
        ):
            from pdf2zh.pdf2zh import main

            self.assertEqual(main(argv), 0)
        return switch, mock_kernel

    def test_default_is_auto(self):
        switch, kernel = self._main(["test.pdf"])
        switch.assert_called_once_with("auto")
        kernel.translate.assert_called_once()

    def test_kernel_flag(self):
        switch, _ = self._main(["test.pdf", "--kernel", "legacy"])
        switch.assert_called_once_with("legacy")

    def test_deprecated_mode_flags_map_to_kernels(self):
        switch, _ = self._main(["test.pdf", "--mode", "fast"])
        switch.assert_called_once_with("legacy")
        switch, _ = self._main(["test.pdf", "--mode", "precise"])
        switch.assert_called_once_with("babeldoc")
        switch, _ = self._main(["test.pdf", "--babeldoc"])
        switch.assert_called_once_with("babeldoc")

    def test_backend_cpu_and_removed_gpu_values(self):
        from pdf2zh.pdf2zh import _load_layout_model, create_parser, parse_args

        for value, expected in (
            ("cpu", "cpu"),
            ("auto", "auto"),
            ("cuda", "auto"),
            ("dml", "auto"),
        ):
            with (
                patch("pdf2zh.doclayout.set_backend") as set_backend,
                patch("pdf2zh.doclayout.OnnxModel"),
                patch("pdf2zh.doclayout.ModelInstance"),
            ):
                _load_layout_model(parse_args(["a.pdf", "--backend", value]))
            set_backend.assert_called_once_with(expected)
        # Downstream UIs list the parser's choices: only the supported ones.
        action = next(a for a in create_parser()._actions if a.dest == "backend")
        self.assertEqual(action.choices, ["auto", "cpu"])

    def test_legacy_only_flags_pick_legacy(self):
        from pdf2zh.pdf2zh import parse_args

        self.assertEqual(parse_args(["--ultrafast"]).kernel, "legacy")
        self.assertEqual(parse_args(["--onnx", "m.onnx"]).kernel, "legacy")

    def test_conflicting_kernel_flags_rejected(self):
        from pdf2zh.pdf2zh import parse_args

        for argv in (
            ["--kernel", "legacy", "--babeldoc"],
            ["--kernel", "babeldoc", "--onnx", "m.onnx"],
        ):
            with self.assertRaises(SystemExit):
                parse_args(argv)

    def test_cli_service_model_syntax_passed_through(self):
        _, kernel = self._main(["test.pdf", "-s", "openai:gpt-4"])
        self.assertEqual(kernel.translate.call_args[0][0].service, "openai:gpt-4")

    def test_json_flag_prints_only_one_json_object(self):
        import io
        import json
        from contextlib import redirect_stdout
        from pdf2zh.kernel.protocol import TranslateResult

        kernel = MagicMock()
        kernel.name = "babeldoc"

        def translate(request, callback=None):
            print("noise from a kernel")  # must not reach stdout
            return [TranslateResult(mono_pdf=Path("/o/a.mono.pdf"), dual_pdf=None)]

        kernel.translate.side_effect = translate
        out = io.StringIO()
        with (
            patch("pdf2zh.kernel.registry.KernelRegistry.switch"),
            patch("pdf2zh.kernel.registry.KernelRegistry.get", return_value=kernel),
            redirect_stdout(out),
        ):
            from pdf2zh.pdf2zh import main

            self.assertEqual(main(["a.pdf", "--json"]), 0)
        payload = json.loads(out.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["kernel"], "babeldoc")
        self.assertEqual(payload["results"][0]["input"], "a.pdf")
        self.assertTrue(payload["results"][0]["mono"].endswith("a.mono.pdf"))
        self.assertIsNone(payload["results"][0]["dual"])

    def test_json_flag_reports_failure(self):
        import io
        import json
        from contextlib import redirect_stdout

        kernel = MagicMock()
        kernel.name = "legacy"
        kernel.translate.side_effect = RuntimeError("boom")
        out = io.StringIO()
        with (
            patch("pdf2zh.kernel.registry.KernelRegistry.switch"),
            patch("pdf2zh.kernel.registry.KernelRegistry.get", return_value=kernel),
            redirect_stdout(out),
        ):
            from pdf2zh.pdf2zh import main

            self.assertEqual(main(["a.pdf", "--json"]), 1)
        self.assertEqual(
            json.loads(out.getvalue()),
            {"ok": False, "kernel": "legacy", "error": "boom"},
        )


if __name__ == "__main__":
    unittest.main()
