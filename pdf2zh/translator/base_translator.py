import contextlib
import logging
from abc import ABC
from abc import abstractmethod

from pdf2zh.translator.base_rate_limiter import BaseRateLimiter
from pdf2zh.translator.cache import TranslationCache

logger = logging.getLogger(__name__)


class BaseTranslator(ABC):
    # Due to cache limitations, name should be within 20 characters.
    # cache.py: translate_engine = CharField(max_length=20)
    name = "base"
    lang_map = {}

    def __init__(self, lang_in, lang_out, ignore_cache, rate_limiter: BaseRateLimiter):
        self.ignore_cache = ignore_cache
        lang_in = self.lang_map.get(lang_in.lower(), lang_in)
        lang_out = self.lang_map.get(lang_out.lower(), lang_out)
        self.lang_in = lang_in
        self.lang_out = lang_out
        self.rate_limiter = rate_limiter

        self.cache = TranslationCache(
            self.name,
            {
                "lang_in": lang_in,
                "lang_out": lang_out,
            },
        )

        self.translate_call_count = 0
        self.translate_cache_call_count = 0

    def __del__(self):
        with contextlib.suppress(Exception):
            logger.info(
                f"{self.name} translate call count: {self.translate_call_count}"
            )
            logger.info(
                f"{self.name} translate cache call count: {self.translate_cache_call_count}",
            )

    def add_cache_impact_parameters(self, k: str, v):
        """
        Add parameters that affect the translation quality to distinguish the translation effects under different parameters.
        :param k: key
        :param v: value
        """
        self.cache.add_params(k, v)

    def translate(self, text, ignore_cache=False):
        """
        Translate the text, and the other part should call this method.
        :param text: text to translate
        :return: translated text
        """
        self.translate_call_count += 1
        if not (self.ignore_cache or ignore_cache):
            cache = self.cache.get(text)
            if cache is not None:
                self.translate_cache_call_count += 1
                return cache
        self.rate_limiter.wait()
        translation = self.do_translate(text)
        if not (self.ignore_cache or ignore_cache):
            self.cache.set(text, translation)
        return translation

    def llm_translate(self, text, ignore_cache=False):
        """
        Translate the text, and the other part should call this method.
        :param text: text to translate
        :return: translated text
        """
        self.translate_call_count += 1
        if not (self.ignore_cache or ignore_cache):
            cache = self.cache.get(text)
            if cache is not None:
                self.translate_cache_call_count += 1
                return cache
        self.rate_limiter.wait()
        translation = self.do_llm_translate(text)
        if not (self.ignore_cache or ignore_cache):
            self.cache.set(text, translation)
        return translation

    @abstractmethod
    def do_llm_translate(self, text):
        """
        Actual translate text, override this method
        :param text: text to translate
        :return: translated text
        """
        raise NotImplementedError

    @abstractmethod
    def do_translate(self, text):
        """
        Actual translate text, override this method
        :param text: text to translate
        :return: translated text
        """
        logger.critical(
            f"Do not call BaseTranslator.do_translate. "
            f"Translator: {self}. "
            f"Text: {text}. ",
        )
        raise NotImplementedError

    def __str__(self):
        return f"{self.name} {self.lang_in} {self.lang_out} {self.model}"

    def get_formular_placeholder(self, placeholder_id: int):
        return "{v" + str(placeholder_id) + "}"

    def get_rich_text_left_placeholder(self, placeholder_id: int):
        return self.get_formular_placeholder(placeholder_id)

    def get_rich_text_right_placeholder(self, placeholder_id: int):
        return self.get_formular_placeholder(placeholder_id + 1)
