from pdf2zh.config.model import SettingsModel
from pdf2zh.translator.base_rate_limiter import BaseRateLimiter
from pdf2zh.translator.base_translator import BaseTranslator
from pdf2zh.translator.rate_limiter.qps_rate_limiter import QPSRateLimiter
from pdf2zh.translator.translator_impl.bing import BingTranslator
from pdf2zh.translator.translator_impl.google import GoogleTranslator
from pdf2zh.translator.translator_impl.openai import OpenAITranslator


def get_rate_limiter(settings: SettingsModel) -> BaseRateLimiter:
    if settings.translation.qps:
        return QPSRateLimiter(settings.translation.qps)
    else:
        return None


def get_translator(settings: SettingsModel) -> BaseTranslator:
    rate_limiter = get_rate_limiter(settings)
    if settings.openai:
        return OpenAITranslator(
            settings,
            rate_limiter,
        )
    if settings.bing:
        return BingTranslator(
            settings,
            rate_limiter,
        )
    if settings.google:
        return GoogleTranslator(
            settings,
            rate_limiter,
        )
    raise ValueError("No translator found")
