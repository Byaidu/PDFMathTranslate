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

from babeldoc.high_level import async_translate as babeldoc_translate
from babeldoc.main import create_progress_handler
from babeldoc.translation_config import TranslationConfig as BabelDOCConfig

from pdf2zh.config import ConfigManager
from pdf2zh.config.model import SettingsModel
from pdf2zh.translator import OpenAITranslator

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


async def main() -> int:
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

    await do_translate(settings)
    return 0


async def do_translate(settings: SettingsModel) -> int:
    assert len(settings.basic.input_files) >= 1, "At least one input file is required"

    for file in list(settings.basic.input_files):
        await do_translate_file(settings, file)

    return 0


async def do_translate_file(settings: SettingsModel, file: Path) -> int:
    translator = settings.get_translator()
    if translator is None:
        raise ValueError("No translator found")

    babeldoc_config = BabelDOCConfig(
        input_file=file,
        font=None,
        pages=settings.translation.pages,
        output_dir=settings.translation.output,
        doc_layout_model=None,
        translator=translator,
        debug=settings.basic.debug,
        lang_in=settings.translation.lang_in,
        lang_out=settings.translation.lang_out,
        no_dual=settings.pdf.no_dual,
        no_mono=settings.pdf.no_mono,
        qps=settings.translation.qps,
        disable_rich_text_translate=not isinstance(translator, OpenAITranslator),
        skip_clean=settings.pdf.skip_clean,
        report_interval=0.5,
    )

    progress_context, progress_handler = create_progress_handler(babeldoc_config)
    # 开始翻译
    with progress_context:
        async for event in babeldoc_translate(babeldoc_config):
            progress_handler(event)
            if babeldoc_config.debug:
                logger.debug(event)
            if event["type"] == "finish":
                result = event["translate_result"]
                logger.info("Translation Result:")
                logger.info(f"  Original PDF: {result.original_pdf_path}")
                logger.info(f"  Time Cost: {result.total_seconds:.2f}s")
                logger.info(f"  Mono PDF: {result.mono_pdf_path or 'None'}")
                logger.info(f"  Dual PDF: {result.dual_pdf_path or 'None'}")
                break

    return 0


def cli():
    sys.exit(asyncio.run(main()))


if __name__ == "__main__":
    cli()
