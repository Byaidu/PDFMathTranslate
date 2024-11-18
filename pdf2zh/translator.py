import html
import logging
import os
import re
from json import dumps, loads

import deepl
import ollama
import openai
import requests
from azure.ai.translation.text import TextTranslationClient
from azure.core.credentials import AzureKeyCredential


class BaseTranslator:
    def __init__(self, service, lang_out, lang_in, model):
        self.service = service
        self.lang_out = lang_out
        self.lang_in = lang_in
        self.model = model

    def translate(self, text) -> str:
        ...

    def __str__(self):
        pass

    def __str__(self):
        return f"{self.service} {self.lang_out} {self.lang_in}"


class GoogleTranslator(BaseTranslator):
    def __init__(self, service, lang_out, lang_in, model):
        lang_out = "zh-CN" if lang_out == "auto" else lang_out
        lang_in = "en" if lang_in == "auto" else lang_in
        super().__init__(service, lang_out, lang_in, model)
        self.session = requests.Session()
        self.base_link = "http://translate.google.com/m"
        self.headers = {
            "User-Agent": "Mozilla/4.0 (compatible;MSIE 6.0;Windows NT 5.1;SV1;.NET CLR 1.1.4322;.NET CLR 2.0.50727;.NET CLR 3.0.04506.30)"
        }

    def translate(self, text):
        text = text[:5000]  # google translate max length
        response = self.session.get(
            self.base_link,
            params={"tl": self.lang_out, "sl": self.lang_in, "q": text},
            headers=self.headers,
        )
        re_result = re.findall(
            r'(?s)class="(?:t0|result-container)">(.*?)<', response.text
        )
        if response.status_code == 400:
            result = 'IRREPARABLE TRANSLATION ERROR'
        elif len(re_result) == 0:
            raise ValueError("Empty translation result")
        else:
            result = html.unescape(re_result[0])
        return result


class DeepLXTranslator(BaseTranslator):
    def __init__(self, service, lang_out, lang_in, model):
        lang_out = "zh" if lang_out == "auto" else lang_out
        lang_in = "en" if lang_in == "auto" else lang_in
        super().__init__(service, lang_out, lang_in, model)
        try:
            auth_key = os.getenv("DEEPLX_AUTH_KEY")
            server_url = (
                "https://api.deeplx.org"
                if not os.getenv("DEEPLX_SERVER_URL")
                else os.getenv("DEEPLX_SERVER_URL")
            )
        except KeyError as e:
            missing_var = e.args[0]
            raise ValueError(
                f"The environment variable '{missing_var}' is required but not set."
            ) from e

        self.session = requests.Session()
        self.base_link = f"{server_url}/{auth_key}/translate"
        self.headers = {
            "User-Agent": "Mozilla/4.0 (compatible;MSIE 6.0;Windows NT 5.1;SV1;.NET CLR 1.1.4322;.NET CLR 2.0.50727;.NET CLR 3.0.04506.30)"
        }

    def translate(self, text):
        text = text[:5000]  # google translate max length
        response = self.session.post(
            self.base_link,
            dumps(
                {
                    "target_lang": self.lang_out,
                    "text": text,
                }
            ),
            headers=self.headers,
        )
        # 1. Status code test
        if response.status_code == 200:
            result = loads(response.text)
        else:
            raise ValueError("HTTP error: " + str(response.status_code))
        # 2. Result test
        try:
            result = result["data"]
            return result
        except KeyError:
            result = ""
            raise ValueError("No valid key in DeepLX's response")
        # 3. Result length check
        if len(result) == 0:
            raise ValueError("Empty translation result")
        return result


class DeepLTranslator(BaseTranslator):
    def __init__(self, service, lang_out, lang_in, model):
        lang_out='ZH' if lang_out=='auto' else lang_out
        lang_in='EN' if lang_in=='auto' else lang_in
        super().__init__(service, lang_out, lang_in, model)
        self.session = requests.Session()
        auth_key = os.getenv('DEEPL_AUTH_KEY')
        server_url = os.getenv('DEEPL_SERVER_URL')
        self.client = deepl.Translator(auth_key, server_url=server_url)

    def translate(self, text):
        response = self.client.translate_text(
            text,
            target_lang=self.lang_out,
            source_lang=self.lang_in
        )
        return response.text


class OllamaTranslator(BaseTranslator):
    def __init__(self, service, lang_out, lang_in, model):
        lang_out='zh-CN' if lang_out=='auto' else lang_out
        lang_in='en' if lang_in=='auto' else lang_in
        super().__init__(service, lang_out, lang_in, model)
        self.options = {"temperature": 0}  # 随机采样可能会打断公式标记
        # OLLAMA_HOST
        self.client = ollama.Client()

    def translate(self, text):
        response = self.client.chat(
            model=self.model,
            options=self.options,
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional,authentic machine translation engine.",
                },
                {
                    "role": "user",
                    "content": f"Translate the following markdown source text to {self.lang_out}. Keep the formula notation $v*$ unchanged. Output translation directly without any additional text.\nSource Text: {text}\nTranslated Text:",
                },
            ],
        )
        return response["message"]["content"].strip()

class OpenAITranslator(BaseTranslator):
    def __init__(self, service, lang_out, lang_in, model):
        lang_out='zh-CN' if lang_out=='auto' else lang_out
        lang_in='en' if lang_in=='auto' else lang_in
        super().__init__(service, lang_out, lang_in, model)
        self.options = {"temperature": 0}  # 随机采样可能会打断公式标记
        # OPENAI_BASE_URL
        # OPENAI_API_KEY
        self.client = openai.OpenAI()

    def translate(self, text) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            **self.options,
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional,authentic machine translation engine.",
                },
                {
                    "role": "user",
                    "content": f"Translate the following markdown source text to {self.lang_out}. Keep the formula notation $v*$ unchanged. Output translation directly without any additional text.\nSource Text: {text}\nTranslated Text:",
                },
            ],
        )
        return response.choices[0].message.content.strip()


class AzureTranslator(BaseTranslator):
    def __init__(self, service, lang_out, lang_in, model):
        lang_out='zh-Hans' if lang_out=='auto' else lang_out
        lang_in='en' if lang_in=='auto' else lang_in
        super().__init__(service, lang_out, lang_in, model)

        try:
            api_key = os.environ["AZURE_APIKEY"]
            endpoint = os.environ["AZURE_ENDPOINT"]
            region = os.environ["AZURE_REGION"]
        except KeyError as e:
            missing_var = e.args[0]
            raise ValueError(f"The environment variable '{missing_var}' is required but not set.") from e

        credential = AzureKeyCredential(api_key)
        self.client = TextTranslationClient(
            endpoint=endpoint, credential=credential, region=region
        )

        # https://github.com/Azure/azure-sdk-for-python/issues/9422
        logger = logging.getLogger("azure.core.pipeline.policies.http_logging_policy")
        logger.setLevel(logging.WARNING)

    def translate(self, text) -> str:
        response = self.client.translate(
            body=[text],
            from_language=self.lang_in,
            to_language=[self.lang_out],
        )

        translated_text = response[0].translations[0].text
        return translated_text
