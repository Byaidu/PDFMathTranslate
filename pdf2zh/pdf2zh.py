#!/usr/bin/env python3
"""A command line tool for extracting text and images from PDF and
output it to plain text, html, xml or tags.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from string import Template

from babeldoc.high_level import async_translate as yadt_translate
from babeldoc.high_level import init as yadt_init
from babeldoc.main import create_progress_handler
from babeldoc.translation_config import TranslationConfig as YadtConfig

from pdf2zh.config import ConfigManager
from pdf2zh.config.model import SettingsModel

logger = logging.getLogger(__name__)


def find_all_files_in_directory(directory_path):
    """
    Recursively search all PDF files in the given directory and return their paths as a list.

    :param directory_path: str, the path to the directory to search
    :return: list of PDF file paths
    """
    directory_path = Path(directory_path)
    # Check if the provided path is a directory
    if not directory_path.is_dir():
        raise ValueError(f"The provided path '{directory_path}' is not a directory.")

    file_paths = []

    # Walk through the directory recursively
    for root, _, files in os.walk(directory_path):
        for file in files:
            # Check if the file is a PDF
            if file.lower().endswith(".pdf"):
                # Append the full file path to the list
                file_paths.append(Path(root) / file)

    return file_paths


async def main(args: list[str] | None = None) -> int:
    from rich.logging import RichHandler

    logging.basicConfig(level=logging.INFO, handlers=[RichHandler()])

    settings = ConfigManager().initialize_config()
    if settings.basic.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # disable httpx, openai, httpcore, http11 logs
    logging.getLogger("httpx").setLevel("CRITICAL")
    logging.getLogger("httpx").propagate = False
    logging.getLogger("openai").setLevel("CRITICAL")
    logging.getLogger("openai").propagate = False
    logging.getLogger("httpcore").setLevel("CRITICAL")
    logging.getLogger("httpcore").propagate = False
    logging.getLogger("http11").setLevel("CRITICAL")
    logging.getLogger("http11").propagate = False

    print(settings)

    if settings.basic.input_files:
        for file in list(settings.basic.input_files):
            new_settings = settings.clone()
            new_settings.basic.input_files = [file]
            await do_translate(new_settings)

    return 0

    if parsed_args.interactive:
        from pdf2zh.gui import setup_gui

        if parsed_args.serverport:
            setup_gui(
                parsed_args.share, parsed_args.authorized, int(parsed_args.serverport)
            )
        else:
            setup_gui(parsed_args.share, parsed_args.authorized)
        return 0

    return 0


async def do_translate(settings: SettingsModel) -> int:
    translator = settings.get_translator()
    if translator is None:
        raise ValueError("No translator found")

    assert len(settings.basic.input_files) == 1, "Only one input file is supported"

    return 0


def yadt_main(parsed_args) -> int:
    if parsed_args.dir:
        untranlate_file = find_all_files_in_directory(parsed_args.files[0])
    else:
        untranlate_file = parsed_args.files
    lang_in = parsed_args.lang_in
    lang_out = parsed_args.lang_out
    ignore_cache = parsed_args.ignore_cache
    outputdir = None
    if parsed_args.output:
        outputdir = parsed_args.output

    # yadt require init before translate
    yadt_init()

    param = parsed_args.service.split(":", 1)
    service_name = param[0]
    service_model = param[1] if len(param) > 1 else None

    envs = {}
    prompt = []

    if parsed_args.prompt:
        try:
            prompt_path = Path(parsed_args.prompt)
            content = prompt_path.read_text(encoding="utf-8")
            prompt = Template(content)
        except Exception as err:
            raise ValueError("prompt error.") from err

    from pdf2zh.translator import AnythingLLMTranslator
    from pdf2zh.translator import ArgosTranslator
    from pdf2zh.translator import AzureOpenAITranslator
    from pdf2zh.translator import AzureTranslator
    from pdf2zh.translator import BingTranslator
    from pdf2zh.translator import DeepLTranslator
    from pdf2zh.translator import DeepLXTranslator
    from pdf2zh.translator import DeepseekTranslator
    from pdf2zh.translator import DifyTranslator
    from pdf2zh.translator import GeminiTranslator
    from pdf2zh.translator import GoogleTranslator
    from pdf2zh.translator import GrokTranslator
    from pdf2zh.translator import GroqTranslator
    from pdf2zh.translator import ModelScopeTranslator
    from pdf2zh.translator import OllamaTranslator
    from pdf2zh.translator import OpenAIlikedTranslator
    from pdf2zh.translator import OpenAITranslator
    from pdf2zh.translator import QwenMtTranslator
    from pdf2zh.translator import SiliconTranslator
    from pdf2zh.translator import TencentTranslator
    from pdf2zh.translator import XinferenceTranslator
    from pdf2zh.translator import ZhipuTranslator

    for translator in [
        GoogleTranslator,
        BingTranslator,
        DeepLTranslator,
        DeepLXTranslator,
        OllamaTranslator,
        XinferenceTranslator,
        AzureOpenAITranslator,
        OpenAITranslator,
        ZhipuTranslator,
        ModelScopeTranslator,
        SiliconTranslator,
        GeminiTranslator,
        AzureTranslator,
        TencentTranslator,
        DifyTranslator,
        AnythingLLMTranslator,
        ArgosTranslator,
        GrokTranslator,
        GroqTranslator,
        DeepseekTranslator,
        OpenAIlikedTranslator,
        QwenMtTranslator,
    ]:
        if service_name == translator.name:
            translator = translator(
                lang_in,
                lang_out,
                service_model,
                envs=envs,
                prompt=prompt,
                ignore_cache=ignore_cache,
            )
            break
    else:
        raise ValueError("Unsupported translation service")
    import asyncio

    for file in untranlate_file:
        file = file.strip("\"'")
        yadt_config = YadtConfig(
            input_file=file,
            font=None,
            pages=",".join(str(x) for x in getattr(parsed_args, "raw_pages", [])),
            output_dir=outputdir,
            doc_layout_model=None,
            translator=translator,
            debug=parsed_args.debug,
            lang_in=lang_in,
            lang_out=lang_out,
            no_dual=False,
            no_mono=False,
            qps=parsed_args.thread,
        )

        async def yadt_translate_coro(yadt_config):
            progress_context, progress_handler = create_progress_handler(yadt_config)
            # 开始翻译
            with progress_context:
                async for event in yadt_translate(yadt_config):
                    progress_handler(event)
                    if yadt_config.debug:
                        logger.debug(event)
                    if event["type"] == "finish":
                        result = event["translate_result"]
                        logger.info("Translation Result:")
                        logger.info(f"  Original PDF: {result.original_pdf_path}")
                        logger.info(f"  Time Cost: {result.total_seconds:.2f}s")
                        logger.info(f"  Mono PDF: {result.mono_pdf_path or 'None'}")
                        logger.info(f"  Dual PDF: {result.dual_pdf_path or 'None'}")
                        break

        asyncio.run(yadt_translate_coro(yadt_config))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
