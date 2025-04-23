from pdf2zh.config import AzureOpenAISettings
from pdf2zh.config import BingSettings
from pdf2zh.config import DeepLSettings
from pdf2zh.config import DeepLXSettings
from pdf2zh.config import DeepSeekSettings
from pdf2zh.config import GeminiSettings
from pdf2zh.config import GoogleSettings
from pdf2zh.config import ModelScopeSettings
from pdf2zh.config import OllamaSettings
from pdf2zh.config import OpenAISettings
from pdf2zh.config import SiliconSettings
from pdf2zh.config import TencentSettings
from pdf2zh.config import XinferenceSettings
from pdf2zh.config import ZhipuSettings
from pdf2zh.config import AzureSettings
from pdf2zh.config.main import ConfigManager
from pdf2zh.config.model import BasicSettings
from pdf2zh.config.model import PDFSettings
from pdf2zh.config.model import SettingsModel
from pdf2zh.config.model import TranslationSettings
from pdf2zh.config.model import WatermarkOutputMode
from pdf2zh.high_level import create_babeldoc_config
from pdf2zh.high_level import do_translate_async_stream
from pdf2zh.high_level import do_translate_file
from pdf2zh.high_level import do_translate_file_async

# from pdf2zh.high_level import translate, translate_stream

__version__ = "2.0.0.rc0"
__author__ = "Byaidu, awwaawwa"
__license__ = "AGPL-3.0"
__maintainer__ = "awwaawwa"
__email__ = "aw@funstory.ai"

__all__ = [
    "SettingsModel",
    "BasicSettings",
    "OpenAISettings",
    "BingSettings",
    "GoogleSettings",
    "DeepLSettings",
    "DeepLXSettings",
    "DeepSeekSettings",
    "OllamaSettings",
    "XinferenceSettings",
    "AzureOpenAISettings",
    "ModelScopeSettings",
    "ZhipuSettings",
    "SiliconSettings",
    "TencentSettings",
    "GeminiSettings",
    "AzureSettings",
    "PDFSettings",
    "TranslationSettings",
    "WatermarkOutputMode",
    "do_translate_file_async",
    "do_translate_file",
    "do_translate_async_stream",
    "create_babeldoc_config",
    "ConfigManager",
]
