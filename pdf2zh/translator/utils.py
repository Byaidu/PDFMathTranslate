from pdf2zh.config.model import BingSettings
from pdf2zh.config.model import GoogleSettings
from pdf2zh.config.model import OpenAISettings
from pdf2zh.config.model import SettingsModel
from pdf2zh.translator.base_rate_limiter import BaseRateLimiter
from pdf2zh.translator.base_translator import BaseTranslator
from pdf2zh.translator.rate_limiter.qps_rate_limiter import QPSRateLimiter


def get_rate_limiter(settings: SettingsModel) -> BaseRateLimiter:
    if settings.translation.qps:
        return QPSRateLimiter(settings.translation.qps)
    else:
        return None


def get_translator(settings: SettingsModel) -> BaseTranslator:
    rate_limiter = get_rate_limiter(settings=settings)
    translator_config = settings.translate_engine_settings
    if isinstance(translator_config, OpenAISettings):
        from pdf2zh.translator.translator_impl.openai import OpenAITranslator

        return OpenAITranslator(
            settings,
            rate_limiter,
        )
    if isinstance(translator_config, BingSettings):
        from pdf2zh.translator.translator_impl.bing import BingTranslator

        return BingTranslator(
            settings,
            rate_limiter,
        )
    if isinstance(translator_config, GoogleSettings):
        from pdf2zh.translator.translator_impl.google import GoogleTranslator

        return GoogleTranslator(
            settings,
            rate_limiter,
        )
    raise ValueError("No translator found")
