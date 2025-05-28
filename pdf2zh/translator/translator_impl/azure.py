from azure.ai.translation.text import TextTranslationClient
from azure.core.credentials import AzureKeyCredential
from pdf2zh.config.model import SettingsModel
from pdf2zh.translator.base_rate_limiter import BaseRateLimiter
from pdf2zh.translator.base_translator import BaseTranslator


class AzureTranslator(BaseTranslator):
    name = "azure"
    lang_map = {"zh": "zh-Hans"}

    def __init__(
        self,
        settings: SettingsModel,
        rate_limiter: BaseRateLimiter,
    ):
        super().__init__(settings, rate_limiter)
        endpoint = settings.translate_engine_settings.azure_endpoint
        api_key = settings.translate_engine_settings.azure_api_key
        credential = AzureKeyCredential(api_key)
        self.client = TextTranslationClient(
            endpoint=endpoint, credential=credential, region="chinaeast2"
        )

    def do_translate(self, text, rate_limit_params: dict = None):
        response = self.client.translate(
            body=[text],
            from_language=self.lang_in,
            to_language=[self.lang_out],
        )
        translated_text = response[0].translations[0].text
        return translated_text
