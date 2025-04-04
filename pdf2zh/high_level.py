import asyncio
import logging
import logging.handlers
import multiprocessing
import multiprocessing.connection
import multiprocessing.queues
import queue
import threading
from collections.abc import AsyncGenerator
from functools import partial
from logging.handlers import QueueHandler
from pathlib import Path

from babeldoc.docvision.table_detection.rapidocr import RapidOCRModel
from babeldoc.high_level import async_translate as babeldoc_translate
from babeldoc.main import create_progress_handler
from babeldoc.translation_config import TranslationConfig as BabelDOCConfig
from babeldoc.translation_config import WatermarkOutputMode as BabelDOCWatermarkMode

from pdf2zh.config.model import SettingsModel
from pdf2zh.translator import get_translator
from pdf2zh.utils import asynchronize

logger = logging.getLogger(__name__)


def _translate_wrapper(
    settings: SettingsModel,
    file: Path,
    pipe_progress_send: multiprocessing.connection.Connection,
    pipe_cancel_message_recv: multiprocessing.connection.Connection,
    logger_queue: multiprocessing.Queue,
):
    logger = logging.getLogger(__name__)

    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("pdfminer").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("peewee").setLevel(logging.WARNING)

    queue_handler = QueueHandler(logger_queue)
    logging.basicConfig(level=logging.INFO, handlers=[queue_handler])

    config = create_babeldoc_config(settings, file)

    def cancel_recv_thread():
        pipe_cancel_message_recv.recv()
        config.cancel_translation()

    cancel_t = threading.Thread(target=cancel_recv_thread, daemon=True)
    cancel_t.start()

    async def translate_wrapper_async():
        try:
            async for event in babeldoc_translate(config):
                logger.debug(f"sub process generate event: {event}")
                if event["type"] == "error":
                    event["error"] = str(event["error"])
                pipe_progress_send.send(event)
                if event["type"] == "finish" or event["type"] == "error":
                    break
        finally:
            logger.debug("sub process send close")
            pipe_progress_send.send(None)
            pipe_progress_send.close()
            logger.debug("sub process close pipe progress send")
            logging.getLogger().removeHandler(queue_handler)
            logger_queue.put(None)
            logger_queue.close()

    asyncio.run(translate_wrapper_async())


async def _translate_in_subprocess(
    settings: SettingsModel,
    file: Path,
):
    # 30 minutes timeout
    cb = asynchronize.AsyncCallback(timeout=30 * 60)

    (pipe_progress_recv, pipe_progress_send) = multiprocessing.Pipe(duplex=False)
    (pipe_cancel_message_recv, pipe_cancel_message_send) = multiprocessing.Pipe(
        duplex=False
    )
    logger_queue = multiprocessing.Queue()
    cancel_event = threading.Event()

    def recv_thread():
        while True:
            if cancel_event.is_set():
                break
            try:
                event = pipe_progress_recv.recv()
                if event is None:
                    logger.debug("recv none event")
                    cb.finished_callback_without_args()
                    break
                cb.step_callback(event)
            except EOFError:
                logger.debug("recv eof error")
                cb.finished_callback_without_args()
                break
            except Exception as e:
                logger.error(f"Error receiving event: {e}")
                break

    def log_thread():
        while True:
            try:
                record = logger_queue.get()
                if record is None:
                    logger.info("Listener stopped.")
                    break
                logger.handle(record)
            except KeyboardInterrupt:
                logger.info("Listener stopped.")
                break
            except queue.Empty:
                logger.info("Listener stopped.")
                break
            except Exception:
                logger.error("Failure in listener_process")

    recv_t = threading.Thread(target=recv_thread)
    recv_t.start()
    log_t = threading.Thread(target=log_thread)
    log_t.start()

    translate_process = multiprocessing.Process(
        target=_translate_wrapper,
        args=(
            settings,
            file,
            pipe_progress_send,
            pipe_cancel_message_recv,
            logger_queue,
        ),
    )
    translate_process.start()
    try:
        async for event in cb:
            yield event.args[0]
    except asyncio.CancelledError:
        logger.info("Process Translation cancelled")
    finally:
        logger.debug("send cancel message")
        pipe_cancel_message_send.send(True)
        logger.debug("close pipe cancel message")
        pipe_cancel_message_send.close()
        pipe_progress_send.send(None)
        logger.debug("set cancel event")
        cancel_event.set()
        translate_process.terminate()
        logger.debug("join translate process")
        translate_process.join(timeout=1)
        if translate_process.is_alive():
            logger.error("Translate process did not finish in time, killing it")
            try:
                translate_process.kill()
                translate_process.join()
                logger.info("Translate process killed")
            except Exception:
                logger.exception("Error killing translate process:")
        logger.debug("join recv thread")
        recv_t.join(timeout=0.1)
        if recv_t.is_alive():
            logger.error("Recv thread did not finish in time")
        logger.debug("translate process exit code: %s", translate_process.exitcode)


def create_babeldoc_config(settings: SettingsModel, file: Path) -> BabelDOCConfig:
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
        skip_scanned_detection=settings.pdf.skip_scanned_detection,
    )
    return babeldoc_config


async def do_translate_async_stream(
    settings: SettingsModel, file: Path | str
) -> AsyncGenerator[dict, None]:
    if isinstance(file, str):
        file = Path(file)

    if settings.basic.input_files:
        logger.warning(
            "settings.basic.input_files is for cli & config, "
            "pdf2zh.highlevel.do_translate_async_stream will ignore this field "
            "and only translate the file pointed to by the file parameter."
        )

    if not file.exists():
        raise FileNotFoundError(f"file {file} not found")

    # 开始翻译
    translate_func = partial(_translate_in_subprocess, settings, file)
    if settings.basic.debug:
        babeldoc_config = create_babeldoc_config(settings, file)
        logger.debug("debug mode, translate in main process")
        translate_func = partial(babeldoc_translate, config=babeldoc_config)
    else:
        logger.info("translate in subprocess")

    async for event in translate_func():
        yield event
        if settings.basic.debug:
            logger.debug(event)
        if event["type"] == "finish" or event["type"] == "error":
            break


async def do_translate_file_async(
    settings: SettingsModel, ignore_error: bool = False
) -> int:
    rich_pbar_config = BabelDOCConfig(
        translator=None,
        lang_in=None,
        lang_out=None,
        input_file=None,
        font=None,
        pages=None,
        output_dir=None,
        doc_layout_model=1,
        use_rich_pbar=True,
    )
    progress_context, progress_handler = create_progress_handler(rich_pbar_config)
    input_files = settings.basic.input_files
    settings.basic.input_files = set()
    for file in input_files:
        logger.info(f"translate file: {file}")
        # 开始翻译
        with progress_context:
            try:
                async for event in do_translate_async_stream(settings, file):
                    progress_handler(event)
                    if settings.basic.debug:
                        logger.debug(event)
                    if event["type"] == "finish":
                        result = event["translate_result"]
                        logger.info("Translation Result:")
                        logger.info(f"  Original PDF: {result.original_pdf_path}")
                        logger.info(f"  Time Cost: {result.total_seconds:.2f}s")
                        logger.info(f"  Mono PDF: {result.mono_pdf_path or 'None'}")
                        logger.info(f"  Dual PDF: {result.dual_pdf_path or 'None'}")
                        break
                    if event["type"] == "error":
                        raise RuntimeError(event["error"])
            except Exception as e:
                logger.error(f"Error translating file {file}: {e}")

                if not ignore_error:
                    raise e

    return 0


def do_translate_file(settings: SettingsModel):
    try:
        asyncio.run(do_translate_file_async(settings))
    except RuntimeError as e:
        if "asyncio.run() cannot be called from a running event loop" in str(e):
            loop = asyncio.get_event_loop()
            loop.run_until_complete(do_translate_file_async(settings))
        else:
            raise e
