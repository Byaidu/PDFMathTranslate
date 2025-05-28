import json

import requests
from pdf2zh.config.model import SettingsModel
from pdf2zh.translator.base_rate_limiter import BaseRateLimiter
from pdf2zh.translator.base_translator import BaseTranslator


class AnythingLLMTranslator(BaseTranslator):
    name = "anythingllm"

    def __init__(
        self,
        settings: SettingsModel,
        rate_limiter: BaseRateLimiter,
    ):
        super().__init__(settings, rate_limiter)
        self.api_url = settings.translate_engine_settings.anythingllm_url
        self.api_key = settings.translate_engine_settings.anythingllm_apikey
        self.headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def do_translate(self, text, rate_limit_params: dict = None):
        messages = self.prompt(text)
        payload = {
            "message": messages,
            "mode": "chat",
            "sessionId": "translation_expert",
        }

        response = requests.post(
            self.api_url, headers=self.headers, data=json.dumps(payload), timeout=60
        )
        response.raise_for_status()
        data = response.json()

        if "textResponse" in data:
            return data["textResponse"].strip()
