import logging

import openai
from babeldoc.document_il.utils.atomic_integer import AtomicInteger
from pdf2zh.config.model import SettingsModel
from pdf2zh.translator.base_rate_limiter import BaseRateLimiter
from pdf2zh.translator.base_translator import BaseTranslator
from tenacity import retry
from tenacity import retry_if_exception_type
from tenacity import stop_after_attempt
from tenacity import wait_exponential

logger = logging.getLogger(__name__)


class QwenMtTranslator(BaseTranslator):
    name = "qwen-mt"

    def __init__(
        self,
        settings: SettingsModel,
        rate_limiter: BaseRateLimiter,
    ):
        super().__init__(settings, rate_limiter)
        self.options = {"temperature": 0}  # 随机采样可能会打断公式标记
        self.client = openai.OpenAI(
            base_url=settings.translate_engine_settings.qwenmt_base_url,
            api_key=settings.translate_engine_settings.qwenmt_api_key,
        )
        self.add_cache_impact_parameters("temperature", self.options["temperature"])
        self.model = settings.translate_engine_settings.qwenmt_model
        self.ali_domain = settings.translate_engine_settings.ali_domains
        self.add_cache_impact_parameters("model", self.model)
        self.add_cache_impact_parameters("prompt", self.prompt(""))
        self.token_count = AtomicInteger()
        self.prompt_token_count = AtomicInteger()
        self.completion_token_count = AtomicInteger()

    def lang_mapping(self, input_lang: str) -> str:
        """
        Mapping the language code to the language code that Aliyun Qwen-Mt model supports.
        Since all existings languagues codes used in gui.py are able to be mapped, the original
        languague code will not be checked.
        """
        langdict = {
            "zh": "Chinese",
            "zh-TW": "Chinese",
            "en": "English",
            "fr": "French",
            "de": "German",
            "ja": "Japanese",
            "ko": "Korean",
            "ru": "Russian",
            "es": "Spanish",
            "it": "Italian",
        }

        return langdict[input_lang]

    def prompt(self, text):
        return [
            {
                "role": "user",
                "content": f"You are a professional,authentic machine translation engine.\n\n;; Treat next line as plain text input and translate it into {self.lang_out}, output translation ONLY. If translation is unnecessary (e.g. proper nouns, codes, {'{{1}}, etc. '}), return the original text. NO explanations. NO notes. Input:\n\n{text}",
            },
        ]

    @retry(
        retry=retry_if_exception_type(openai.RateLimitError),
        stop=stop_after_attempt(100),
        wait=wait_exponential(multiplier=1, min=1, max=15),
        before_sleep=lambda retry_state: logger.warning(
            f"RateLimitError, retrying in {retry_state.next_action.sleep} seconds... "
            f"(Attempt {retry_state.attempt_number}/100)"
        ),
    )
    def do_translate(self, text, rate_limit_params: dict = None):
        translation_options = {
            "source_lang": self.lang_mapping(self.lang_in),
            "target_lang": self.lang_mapping(self.lang_out),
            "domains": self.ali_domain,
        }
        response = self.client.chat.completions.create(
            model=self.model,
            **self.options,
            messages=[{"role": "user", "content": self.prompt(text)}],
            extra_body={"translation_options": translation_options},
        )
        message = response.choices[0].message.content.strip()
        message = self._remove_cot_content(message)
        return message

    @retry(
        retry=retry_if_exception_type(openai.RateLimitError),
        stop=stop_after_attempt(100),
        wait=wait_exponential(multiplier=1, min=1, max=15),
        before_sleep=lambda retry_state: logger.warning(
            f"RateLimitError, retrying in {retry_state.next_action.sleep} seconds... "
            f"(Attempt {retry_state.attempt_number}/100)"
        ),
    )
    def do_llm_translate(self, text, rate_limit_params: dict = None):
        if text is None:
            return None

        translation_options = {
            "source_lang": self.lang_mapping(self.lang_in),
            "target_lang": self.lang_mapping(self.lang_out),
            "domains": self.ali_domain,
        }
        response = self.client.chat.completions.create(
            model=self.model,
            **self.options,
            messages=[
                {
                    "role": "user",
                    "content": text,
                },
            ],
            extra_body={"translation_options": translation_options},
        )
        self.token_count.inc(response.usage.total_tokens)
        self.prompt_token_count.inc(response.usage.prompt_tokens)
        self.completion_token_count.inc(response.usage.completion_tokens)
        message = response.choices[0].message.content.strip()
        message = self._remove_cot_content(message)
        return message
