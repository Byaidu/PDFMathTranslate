import requests
from pdf2zh.config.model import SettingsModel
from pdf2zh.translator.base_rate_limiter import BaseRateLimiter
from pdf2zh.translator.base_translator import BaseTranslator


class DeepLXTranslator(BaseTranslator):
    # https://github.com/immersive-translate/old-immersive-translate/blob/6df13da22664bea2f51efe5db64c63aca59c4e79/src/background/translationService.js
    name = "deeplx"
    lang_map = {"zh": "zh-Hans"}

    def __init__(
        self,
        settings: SettingsModel,
        rate_limiter: BaseRateLimiter,
    ):
        super().__init__(settings, rate_limiter)
        self.endpoint = settings.translate_engine_settings.deeplx_endpoint
        self.session = requests.Session()
        auth_key = settings.translate_engine_settings.deeplx_access_token
        if auth_key:
            self.endpoint = f"{self.endpoint}?token={auth_key}"

    def do_translate(self, text, rate_limit_params: dict = None):
        response = self.session.post(
            self.endpoint,
            json={
                "source_lang": self.lang_in,
                "target_lang": self.lang_out,
                "text": text,
            },
        )
        response.raise_for_status()
        return response.json()["data"]
