import asyncio
import logging
import logging.handlers
import multiprocessing
import multiprocessing.connection
import multiprocessing.queues
import platform
import queue
import threading
import traceback
from collections.abc import AsyncGenerator
from functools import partial
from logging.handlers import QueueHandler
from pathlib import Path

from babeldoc.docvision.table_detection.rapidocr import RapidOCRModel
from babeldoc.high_level import async_translate as babeldoc_translate
from babeldoc.main import create_progress_handler
from babeldoc.translation_config import TranslationConfig as BabelDOCConfig
from babeldoc.translation_config import WatermarkOutputMode as BabelDOCWatermarkMode
from rich.logging import RichHandler

from pdf2zh.config.model import SettingsModel
from pdf2zh.translator import get_translator
from pdf2zh.utils import asynchronize


# Custom exception classes for structured error handling
class TranslationError(Exception):
    """Base class for all translation-related errors."""

    def __reduce__(self):
        """Support for pickling the exception when passing between processes."""
        return (self.__class__, (str(self),))


class BabeldocError(TranslationError):
    """Error originating from the babeldoc library."""

    def __init__(self, message, original_error=None):
        super().__init__(message)
        self.original_error = original_error

    def __reduce__(self):
        """Support for pickling the exception when passing between processes."""
        return (self.__class__, (str(self), self.original_error))

    def __str__(self):
        if self.original_error:
            return f"{super().__str__()} - Original error: {self.original_error}"
        return super().__str__()


class SubprocessError(TranslationError):
    """Error occurring in the translation subprocess outside of babeldoc."""

    def __init__(self, message, traceback_str=None):
        super().__init__(message)
        self.traceback_str = traceback_str

    def __reduce__(self):
        """Support for pickling the exception when passing between processes."""
        return (self.__class__, (str(self), self.traceback_str))

    def __str__(self):
        if self.traceback_str:
            return f"{super().__str__()}\nTraceback: {self.traceback_str}"
        return super().__str__()


class IPCError(TranslationError):
    """Error in inter-process communication."""

    def __init__(self, message, details=None):
        super().__init__(message)
        self.details = details

    def __reduce__(self):
        """Support for pickling the exception when passing between processes."""
        return (self.__class__, (str(self), self.details))

    def __str__(self):
        if self.details:
            return f"{super().__str__()} - Details: {self.details}"
        return super().__str__()


class SubprocessCrashError(TranslationError):
    """Error occurring when the subprocess crashes unexpectedly."""

    def __init__(self, message, exit_code=None):
        super().__init__(message)
        self.exit_code = exit_code

    def __reduce__(self):
        """Support for pickling the exception when passing between processes."""
        return (self.__class__, (str(self), self.exit_code))

    def __str__(self):
        if self.exit_code is not None:
            return f"{super().__str__()} (exit code: {self.exit_code})"
        return super().__str__()


logger = logging.getLogger(__name__)


def _translate_wrapper(
    settings: SettingsModel,
    file: Path,
    pipe_progress_send: multiprocessing.connection.Connection,
    pipe_cancel_message_recv: multiprocessing.connection.Connection,
    logger_queue: multiprocessing.Queue,
):
    logger = logging.getLogger(__name__)

    try:
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
            try:
                pipe_cancel_message_recv.recv()
                logger.debug("Cancel signal received in subprocess")
                config.cancel_translation()
            except Exception as e:
                logger.error(f"Error in cancel_recv_thread: {e}")

        cancel_t = threading.Thread(target=cancel_recv_thread, daemon=True)
        cancel_t.start()

        async def translate_wrapper_async():
            try:
                async for event in babeldoc_translate(config):
                    logger.debug(f"sub process generate event: {event}")
                    if event["type"] == "error":
                        # Convert babeldoc error to structured exception
                        error_msg = str(event.get("error", "Unknown babeldoc error"))
                        error = BabeldocError(
                            message=f"Babeldoc translation error: {error_msg}",
                            original_error=error_msg,
                        )
                        pipe_progress_send.send(error)
                        break
                    # Send normal progress events as before
                    pipe_progress_send.send(event)
                    if event["type"] == "finish":
                        break
            except Exception as e:
                # Capture non-babeldoc errors during translation
                tb_str = traceback.format_exc()
                logger.error(f"Error in translate_wrapper_async: {e}\n{tb_str}")
                error = SubprocessError(
                    message=f"Error during translation process: {e}",
                    traceback_str=tb_str,
                )
                try:
                    pipe_progress_send.send(error)
                except Exception as pipe_err:
                    logger.error(f"Failed to send error through pipe: {pipe_err}")

        # Run the async translation in the subprocess's event loop
        try:
            asyncio.run(translate_wrapper_async())
        except Exception as e:
            # Capture errors that might occur outside the async context
            tb_str = traceback.format_exc()
            logger.error(f"Error running async translation: {e}\n{tb_str}")
            error = SubprocessError(
                message=f"Failed to run translation process: {e}", traceback_str=tb_str
            )
            try:
                pipe_progress_send.send(error)
            except Exception as pipe_err:
                logger.error(f"Failed to send error through pipe: {pipe_err}")
    except Exception as e:
        # Capture any errors during setup or initialization
        tb_str = traceback.format_exc()
        logger.error(f"Subprocess initialization error: {e}\n{tb_str}")
        try:
            error = SubprocessError(
                message=f"Translation subprocess initialization error: {e}",
                traceback_str=tb_str,
            )
            pipe_progress_send.send(error)
        except Exception as pipe_err:
            logger.error(f"Failed to send error through pipe: {pipe_err}")
    finally:
        logger.debug("sub process send close")
        try:
            pipe_progress_send.send(None)
            pipe_progress_send.close()
            logger.debug("sub process close pipe progress send")
        except Exception as e:
            logger.error(f"Error closing progress pipe: {e}")

        try:
            logging.getLogger().removeHandler(queue_handler)
            logging.getLogger().addHandler(RichHandler())
            logger_queue.put(None)
            logger_queue.close()
        except Exception as e:
            logger.error(f"Error closing logger queue: {e}")


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

                # Handle different types of messages from the subprocess
                if isinstance(event, TranslationError):
                    # Received a structured error object
                    logger.error(f"Received error from subprocess: {event}")
                    cb.error_callback(event)
                    break
                elif isinstance(event, dict):
                    # Process normal progress events
                    cb.step_callback(event)
                else:
                    # Unexpected message type
                    logger.warning(
                        f"Unexpected message type from subprocess: {type(event)}"
                    )
                    error = IPCError(f"Unexpected message type: {type(event)}")
                    cb.error_callback(error)
                    break
            except EOFError:
                logger.debug("recv eof error")
                error = IPCError("Connection to subprocess was closed unexpectedly")
                cb.error_callback(error)
                break
            except Exception as e:
                logger.error(f"Error receiving event: {e}")
                error = IPCError(f"IPC error: {e}", details=str(e))
                cb.error_callback(error)
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
                break

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
            # Check for errors before yielding events
            if cb.has_error():
                # Let AsyncCallback.__anext__ raise the error
                # This will break out of the loop
                break
            yield event.args[0]
    except asyncio.CancelledError:
        logger.info("Process Translation cancelled")
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received in main process")
    finally:
        logger.debug("send cancel message")
        try:
            pipe_cancel_message_send.send(True)
        except (OSError, BrokenPipeError) as e:
            logger.debug(f"Failed to send cancel message: {e}")
        logger.debug("close pipe cancel message")
        try:
            pipe_cancel_message_send.close()
        except Exception as e:
            logger.debug(f"Failed to close pipe_cancel_message_send: {e}")

        try:
            pipe_progress_send.send(None)
        except (OSError, BrokenPipeError) as e:
            logger.debug(f"Failed to send None to pipe_progress_send: {e}")

        logger.debug("set cancel event")
        cancel_event.set()

        # 关闭接收端管道以中断 recv_thread 中的阻塞接收
        try:
            pipe_progress_recv.close()
            logger.debug("closed pipe_progress_recv")
        except Exception as e:
            logger.debug(f"Failed to close pipe_progress_recv: {e}")

        # 终止子进程，使用超时防止卡住
        translate_process.join(timeout=2)
        logger.debug("join translate process")
        if translate_process.is_alive():
            logger.info("Translate process did not finish in time, terminate it")
            translate_process.terminate()
            translate_process.join(timeout=1)
        if translate_process.is_alive():
            logger.info("Translate process did not finish in time, killing it")
            try:
                translate_process.kill()
                translate_process.join(timeout=1)
                logger.info("Translate process killed")
            except Exception as e:
                logger.exception(f"Error killing translate process: {e}")

        # 等待接收线程，使用超时防止卡住
        logger.debug("join recv thread")
        recv_t.join(timeout=2)
        if recv_t.is_alive():
            logger.warning("Recv thread did not finish in time")

        # 等待日志线程，使用超时防止卡住
        log_t.join(timeout=1)
        if log_t.is_alive():
            logger.warning("Log thread did not finish in time")

        # 尝试关闭日志队列
        try:
            logger_queue.put(None)
            logger_queue.close()
        except Exception as e:
            logger.debug(f"Failed to close logger_queue: {e}")

        logger.debug("translate process exit code: %s", translate_process.exitcode)

        # Check if the process crashed but no error was captured through IPC
        if translate_process.exitcode not in (0, None) and not cb.has_error():
            error = SubprocessCrashError(
                f"Translation subprocess crashed with exit code {translate_process.exitcode}",
                exit_code=translate_process.exitcode,
            )
            # We need to raise the error as we're outside the async for loop now
            raise error
        elif cb.has_error():
            # If we have a stored error but haven't raised it yet (exited the loop normally)
            # re-raise it now
            # Note: In most cases, this won't execute because the error would already have been
            # raised by AsyncCallback.__anext__
            raise cb.error


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

    # Windows 平台上不使用子进程翻译，因为 Windows 上的 multiprocessing 实现与 Unix 平台有差异，
    # 在某些情况下可能导致管道通信和进程管理的问题
    if settings.basic.debug or platform.system() == "Windows":
        babeldoc_config = create_babeldoc_config(settings, file)
        if settings.basic.debug:
            logger.debug("debug mode, translate in main process")
        else:
            logger.info(
                "Windows platform detected, translating in main process to avoid subprocess issues"
            )
        translate_func = partial(babeldoc_translate, translation_config=babeldoc_config)
    else:
        logger.info("translate in subprocess")

    try:
        async for event in translate_func():
            yield event
            if settings.basic.debug:
                logger.debug(event)
            if event["type"] == "finish":
                break
    except TranslationError as e:
        # Log and re-raise structured errors
        logger.error(f"Translation error: {e}")
        if isinstance(e, BabeldocError) and e.original_error:
            logger.error(f"Original babeldoc error: {e.original_error}")
        elif isinstance(e, SubprocessError) and e.traceback_str:
            logger.error(f"Subprocess traceback: {e.traceback_str}")
        # Create an error event to yield to client code
        error_event = {
            "type": "error",
            "error": str(e),
            "error_type": e.__class__.__name__,
            "details": getattr(e, "original_error", "")
            or getattr(e, "traceback_str", "")
            or "",
        }
        yield error_event
        raise  # Re-raise the exception so that the caller can handle it if needed


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
    assert len(input_files) >= 1, "At least one input file is required"
    settings.basic.input_files = set()

    error_count = 0

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
                        error_msg = event.get("error", "Unknown error")
                        error_type = event.get("error_type", "UnknownError")
                        details = event.get("details", "")

                        logger.error(f"Error translating file {file}: {error_msg}")
                        logger.error(f"Error type: {error_type}")
                        if details:
                            logger.error(f"Error details: {details}")

                        error_count += 1
                        if not ignore_error:
                            raise RuntimeError(f"Translation error: {error_msg}")
                        break
            except TranslationError as e:
                # Already logged in do_translate_async_stream
                error_count += 1
                if not ignore_error:
                    raise
            except Exception as e:
                logger.error(f"Error translating file {file}: {e}")
                error_count += 1
                if not ignore_error:
                    raise

    return error_count


def do_translate_file(settings: SettingsModel, ignore_error: bool = False) -> int:
    """
    Translate files synchronously, returning the number of errors encountered.

    Args:
        settings: Translation settings
        ignore_error: If True, continue translating other files when an error occurs

    Returns:
        Number of errors encountered during translation

    Raises:
        TranslationError: If a translation error occurs and ignore_error is False
        Exception: For other errors if ignore_error is False
    """
    try:
        return asyncio.run(do_translate_file_async(settings, ignore_error))
    except KeyboardInterrupt:
        logger.info("Translation interrupted by user (Ctrl+C)")
        return 1  # Return error count = 1 to indicate interruption
    except RuntimeError as e:
        # Handle the case where run() is called from a running event loop
        if "asyncio.run() cannot be called from a running event loop" in str(e):
            loop = asyncio.get_event_loop()
            try:
                return loop.run_until_complete(
                    do_translate_file_async(settings, ignore_error)
                )
            except KeyboardInterrupt:
                logger.info("Translation interrupted by user (Ctrl+C) in event loop")
                return 1  # Return error count = 1 to indicate interruption
        else:
            raise
