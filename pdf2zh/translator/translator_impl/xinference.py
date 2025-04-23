import logging

import xinference_client
from pdf2zh.config.model import SettingsModel
from pdf2zh.translator.base_rate_limiter import BaseRateLimiter
from pdf2zh.translator.base_translator import BaseTranslator
from tenacity import retry
from tenacity import retry_if_exception_type
from tenacity import stop_after_attempt
from tenacity import wait_exponential
from xinference_client import RESTfulClient as Client

logger = logging.getLogger(__name__)


class XinferenceTranslator(BaseTranslator):
    name = "xinference"

    def __init__(
        self,
        settings: SettingsModel,
        rate_limiter: BaseRateLimiter,
    ):
        super().__init__(settings, rate_limiter)
        self.options = {
            "temperature": 0,
        }  # 随机采样可能会打断公式标记
        self.client = Client(
            host=settings.translate_engine_settings.xinference_host,
        )
        self.add_cache_impact_parameters("temperature", self.options["temperature"])
        self.model = settings.translate_engine_settings.xinference_model
        self.add_cache_impact_parameters("model", self.model)
        self.add_cache_impact_parameters("prompt", self.prompt(""))

    @retry(
        retry=retry_if_exception_type(xinference_client.RuntimeError),
        stop=stop_after_attempt(100),
        wait=wait_exponential(multiplier=1, min=1, max=15),
        before_sleep=lambda retry_state: logger.warning(
            f"RateLimitError, retrying in {retry_state.next_action.sleep} seconds... "
            f"(Attempt {retry_state.attempt_number}/100)"
        ),
    )
    def do_translate(self, text, rate_limit_params: dict = None) -> str:
        for model in self.model.split(";"):
            try:
                xf_model = self.client.get_model(model)
                xf_prompt = self.prompt(text)
                response = xf_model.chat(
                    generate_config=self.options,
                    messages=xf_prompt,
                )

                response = response["choices"][0]["message"]["content"].replace(
                    "<end_of_turn>", ""
                )
                return response.strip()
            except Exception as e:
                logger.error(e)
        raise Exception("All models failed")

    def prompt(self, text):
        return [
            {
                "role": "user",
                "content": f"You are a professional,authentic machine translation engine.\n\n;; Treat next line as plain text input and translate it into {self.lang_out}, output translation ONLY. If translation is unnecessary (e.g. proper nouns, codes, {'{{1}}, etc. '}), return the original text. NO explanations. NO notes. Input:\n\n{text}",
            },
        ]

    @retry(
        retry=retry_if_exception_type(xinference_client.RuntimeError),
        stop=stop_after_attempt(100),
        wait=wait_exponential(multiplier=1, min=1, max=15),
        before_sleep=lambda retry_state: logger.warning(
            f"RateLimitError, retrying in {retry_state.next_action.sleep} seconds... "
            f"(Attempt {retry_state.attempt_number}/100)"
        ),
    )
    def do_llm_translate(self, text, rate_limit_params: dict = None):
        for model in self.model.split(";"):
            try:
                xf_model = self.client.get_model(model)
                xf_prompt = [
                    {
                        "role": "user",
                        "content": text,
                    },
                ]
                response = xf_model.chat(
                    generate_config=self.options,
                    messages=xf_prompt,
                )

                response = response["choices"][0]["message"]["content"].replace(
                    "<end_of_turn>", ""
                )
                return response.strip()
            except Exception as e:
                logger.error(e)
        raise Exception("All models failed")
