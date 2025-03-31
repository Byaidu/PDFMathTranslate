import logging
from pathlib import Path

from babeldoc.docvision.table_detection.rapidocr import RapidOCRModel
from babeldoc.high_level import async_translate as babeldoc_translate
from babeldoc.main import create_progress_handler
from babeldoc.translation_config import TranslationConfig as BabelDOCConfig
from babeldoc.translation_config import WatermarkOutputMode as BabelDOCWatermarkMode

from pdf2zh.config.model import SettingsModel
from pdf2zh.translator import get_translator

logger = logging.getLogger(__name__)


async def do_translate_file(settings: SettingsModel, file: Path) -> int:
    translator = get_translator(settings)
    if translator is None:
        raise ValueError("No translator found")

    # 设置分割策略
    split_strategy = None
    if settings.pdf.max_pages_per_part:
        split_strategy = BabelDOCConfig.create_max_pages_per_part_split_strategy(
            settings.pdf.max_pages_per_part
        )

    # 设置水印模式
    watermark_mode = BabelDOCWatermarkMode[
        settings.pdf.watermark_output_mode.value.title()
    ]
    table_model = None
    if settings.pdf.translate_table_text:
        table_model = RapidOCRModel()

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
        # 传递原来缺失的参数
        formular_font_pattern=settings.pdf.formular_font_pattern,
        formular_char_pattern=settings.pdf.formular_char_pattern,
        split_short_lines=settings.pdf.split_short_lines,
        short_line_split_factor=settings.pdf.short_line_split_factor,
        disable_rich_text_translate=settings.pdf.disable_rich_text_translate,
        dual_translate_first=settings.pdf.dual_translate_first,
        enhance_compatibility=settings.pdf.enhance_compatibility,
        use_alternating_pages_dual=settings.pdf.use_alternating_pages_dual,
        watermark_output_mode=watermark_mode,
        min_text_length=settings.translation.min_text_length,
        report_interval=settings.report_interval,
        skip_clean=settings.pdf.skip_clean,
        # 添加分割策略
        split_strategy=split_strategy,
        # 添加表格模型，仅在需要翻译表格时
        table_model=table_model,
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
