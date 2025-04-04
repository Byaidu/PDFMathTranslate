import logging

from pdf2zh.config.model import SettingsModel
from pdf2zh.high_level import create_babeldoc_config
from pdf2zh.high_level import do_translate_async_stream
from pdf2zh.high_level import do_translate_file
from pdf2zh.high_level import do_translate_file_async

# from pdf2zh.high_level import translate, translate_stream

log = logging.getLogger(__name__)

__version__ = "2.0.0.rc0"
__author__ = "Byaidu"
# __all__ = ["translate", "translate_stream"]
__all__ = [
    "SettingsModel",
    "do_translate_file_async",
    "do_translate_file",
    "do_translate_async_stream",
    "create_babeldoc_config",
]
