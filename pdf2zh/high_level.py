import logging
from pathlib import Path

from babeldoc.high_level import async_translate as babeldoc_translate
from babeldoc.main import create_progress_handler
from babeldoc.translation_config import TranslationConfig as BabelDOCConfig

from pdf2zh.config.model import SettingsModel
from pdf2zh.translator import get_translator
from pdf2zh.translator.translator_impl.openai import OpenAITranslator

logger = logging.getLogger(__name__)


async def do_translate_file(settings: SettingsModel, file: Path) -> int:
    translator = get_translator(settings)
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
