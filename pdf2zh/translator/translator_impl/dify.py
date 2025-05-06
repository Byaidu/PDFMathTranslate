import json

import requests
from pdf2zh.config.model import SettingsModel
from pdf2zh.translator.base_rate_limiter import BaseRateLimiter
from pdf2zh.translator.base_translator import BaseTranslator


class DifyTranslator(BaseTranslator):
    name = "dify"

    def __init__(
        self,
        settings: SettingsModel,
        rate_limiter: BaseRateLimiter,
    ):
        super().__init__(settings, rate_limiter)
        self.api_url = settings.translate_engine_settings.dify_url
        self.api_key = settings.translate_engine_settings.dify_apikey
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def do_translate(self, text, rate_limit_params: dict = None):
        payload = {
            "inputs": {
                "lang_out": self.lang_out,
                "lang_in": self.lang_in,
                "text": text,
            },
            "response_mode": "blocking",
            "user": "translator-service",
        }

        response = requests.post(
            self.api_url, headers=self.headers, data=json.dumps(payload), timeout=60
        )
        response.raise_for_status()
        data = response.json()

        return data.get("data", {}).get("outputs", {}).get("text", [])
