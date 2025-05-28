import deepl
from pdf2zh.config.model import SettingsModel
from pdf2zh.translator.base_rate_limiter import BaseRateLimiter
from pdf2zh.translator.base_translator import BaseTranslator


class DeepLTranslator(BaseTranslator):
    # https://github.com/immersive-translate/old-immersive-translate/blob/6df13da22664bea2f51efe5db64c63aca59c4e79/src/background/translationService.js
    name = "deepl"
    lang_map = {"zh": "zh-Hans"}

    def __init__(
        self,
        settings: SettingsModel,
        rate_limiter: BaseRateLimiter,
    ):
        super().__init__(settings, rate_limiter)
        self.client = deepl.Translator(
            settings.translate_engine_settings.deepl_auth_key
        )

    def do_translate(self, text, rate_limit_params: dict = None):
        response = self.client.translate_text(
            text, target_lang=self.lang_out, source_lang=self.lang_in
        )
        return response.text
