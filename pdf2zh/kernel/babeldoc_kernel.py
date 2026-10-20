"""BabelDOC kernel — runs BabelDOC in-process with pdf2zh translation services."""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import os
import re
import sys
import threading
from pathlib import Path
from string import Template
from typing import Any, Optional

from pdf2zh.kernel.protocol import TranslateRequest, TranslateResult

logger = logging.getLogger(__name__)

# pdf2zh translators whose client speaks the OpenAI chat API but which are
# dedicated MT models rather than general LLMs.
_NON_LLM_SERVICES = {"qwen-mt"}


_layout_model = None
_layout_lock = threading.Lock()


def layout_model():
    """BabelDOC's ONNX layout model, loaded once per process (takes seconds)."""
    global _layout_model
    with _layout_lock:
        if _layout_model is None:
            from babeldoc.docvision.doclayout import DocLayoutModel

            _layout_model = DocLayoutModel.load_onnx()
        return _layout_model


def pages_to_babeldoc(pages: Optional[list[int] | str]) -> Optional[str]:
    """Convert 0-based page indexes to BabelDOC's 1-based "1,3,5" spec."""
    if not pages:
        return None
    if isinstance(pages, str):
        return pages
    return ",".join(str(p + 1) for p in pages)


def _babeldoc_base():
    from babeldoc.translator.translator import BaseTranslator

    return BaseTranslator


def create_babeldoc_translator(translator: Any, ignore_cache: bool = False):
    """Wrap a pdf2zh translator in BabelDOC's translator interface.

    BabelDOC detects LLM support by calling ``do_llm_translate(None)``: services
    with an OpenAI-compatible client get BabelDOC's LLM prompts, the rest fall
    back to plain ``do_translate``.
    """

    class BabelDOCTranslator(_babeldoc_base()):
        # BabelDOC's cache limits names to 20 characters.
        name = f"pdf2zh-{translator.name}"[:20]

        def __init__(self):
            super().__init__(translator.lang_in, translator.lang_out, ignore_cache)
            self.translator = translator
            self.model = translator.model
            self.add_cache_impact_parameters("model", translator.model)

        def do_translate(self, text, rate_limit_params: dict = None):
            return self.translator.do_translate(text)

        def do_llm_translate(self, text, rate_limit_params: dict = None):
            import openai

            client = getattr(self.translator, "client", None)
            if (
                not isinstance(client, openai.OpenAI)
                or self.translator.name in _NON_LLM_SERVICES
            ):
                raise NotImplementedError
            if text is None:
                return None
            response = client.chat.completions.create(
                model=self.translator.model,
                **self.translator.options,
                messages=[{"role": "user", "content": text}],
            )
            content = response.choices[0].message.content.strip()
            think_filter = getattr(self.translator, "think_filter_regex", None)
            if isinstance(think_filter, re.Pattern):
                content = think_filter.sub("", content, count=1).strip()
            return content

    return BabelDOCTranslator()


class BabelDOCKernel:
    """Kernel adapter for BabelDOC, the optional layout-preserving engine."""

    @property
    def name(self) -> str:
        return "babeldoc"

    @property
    def version(self) -> str:
        if not self.is_available():
            return "unknown"
        from importlib.metadata import version

        return version("babeldoc")

    def is_available(self) -> bool:
        # BabelDOC 0.6 supports Python <3.14; installed there anyway (uv ignores
        # its upper bound), it fails on import.
        return (
            sys.version_info < (3, 14)
            and importlib.util.find_spec("babeldoc") is not None
        )

    def warm_up(self) -> None:
        from babeldoc.format.pdf.high_level import init

        init()
        layout_model()

    def translate(
        self,
        request: TranslateRequest,
        callback: Any = None,
        cancellation_event: Optional[asyncio.Event] = None,
    ) -> list[TranslateResult]:
        return asyncio.run(self.translate_async(request, callback, cancellation_event))

    async def translate_async(
        self,
        request: TranslateRequest,
        callback: Any = None,
        cancellation_event: Optional[asyncio.Event] = None,
    ) -> list[TranslateResult]:
        from babeldoc.format.pdf.high_level import async_translate, init
        from babeldoc.format.pdf.translation_config import TranslationConfig
        from babeldoc.main import create_progress_handler

        from pdf2zh.converter_docx import convert_to_pdf, is_convertible
        from pdf2zh.translator import create_translator

        init()
        translator = create_babeldoc_translator(
            create_translator(
                request.service,
                request.lang_in,
                request.lang_out,
                envs=request.envs,
                prompt=Template(request.prompt) if request.prompt else None,
                ignore_cache=request.ignore_cache,
            ),
            ignore_cache=request.ignore_cache,
        )

        results = []
        for file in request.files:
            file = file.strip("\"'")
            converted = convert_to_pdf(file) if is_convertible(file) else None
            config = TranslationConfig(
                translator=translator,
                input_file=converted or file,
                lang_in=request.lang_in,
                lang_out=request.lang_out,
                doc_layout_model=layout_model(),
                pages=pages_to_babeldoc(request.pages),
                output_dir=request.output or None,
                no_dual=request.no_dual,
                debug=request.debug,
                qps=request.thread,
                formular_font_pattern=request.vfont or None,
                formular_char_pattern=request.vchar or None,
                enhance_compatibility=request.compatible,
            )
            try:
                results.append(
                    await self._run(
                        config,
                        async_translate,
                        create_progress_handler,
                        callback,
                        cancellation_event,
                    )
                )
            finally:
                if converted:
                    try:
                        os.unlink(converted)
                    except OSError:
                        pass
        return results

    @staticmethod
    async def _run(
        config, async_translate, create_progress_handler, callback, cancellation_event
    ) -> TranslateResult:
        if callback is None:
            progress_context, handler = create_progress_handler(config)
        else:
            progress_context, handler = None, callback

        async def consume() -> TranslateResult:
            async for event in async_translate(config):
                if cancellation_event is not None and cancellation_event.is_set():
                    config.cancel_translation()
                handler(event)
                if event["type"] == "error":
                    raise RuntimeError(event.get("error", "BabelDOC failed"))
                if event["type"] == "finish":
                    result = event["translate_result"]
                    return TranslateResult(
                        mono_pdf=_path(result.mono_pdf_path),
                        dual_pdf=_path(result.dual_pdf_path),
                        time_cost=getattr(result, "total_seconds", 0.0) or 0.0,
                    )
            raise RuntimeError("BabelDOC finished without a result")

        if progress_context is None:
            return await consume()
        with progress_context:
            return await consume()


def _path(value) -> Optional[Path]:
    return Path(value) if value else None
