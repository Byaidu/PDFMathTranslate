import html
import logging
import os
import re
import unicodedata

import deepl
import ollama
import openai
import requests
from azure.ai.translation.text import TextTranslationClient
from azure.core.credentials import AzureKeyCredential
from tencentcloud.common import credential
from tencentcloud.tmt.v20180321.tmt_client import TmtClient
from tencentcloud.tmt.v20180321.models import TextTranslateRequest
from tencentcloud.tmt.v20180321.models import TextTranslateResponse


def remove_control_characters(s):
    return "".join(ch for ch in s if unicodedata.category(ch)[0] != "C")


class BaseTranslator:
    envs = {}

    def __init__(self, service, lang_out, lang_in, model):
        self.service = service
        self.lang_out = lang_out
        self.lang_in = lang_in
        self.model = model

    def translate(self, text):
        pass

    def prompt(self, text):
        return [
            {
                "role": "system",
                "content": "You are a professional,authentic machine translation engine.",
            },
            {
                "role": "user",
                "content": f"Translate the following markdown source text to {self.lang_out}. Keep the formula notation $v*$ unchanged. Output translation directly without any additional text.\nSource Text: {text}\nTranslated Text:",  # noqa: E501
            },
        ]

    def __str__(self):
        return f"{self.service} {self.lang_out} {self.lang_in}"


class GoogleTranslator(BaseTranslator):
    def __init__(self, service, lang_out, lang_in, model):
        lang_out = "zh-CN" if lang_out == "auto" else lang_out
        lang_in = "en" if lang_in == "auto" else lang_in
        super().__init__(service, lang_out, lang_in, model)
        self.session = requests.Session()
        self.endpoint = "http://translate.google.com/m"
        self.headers = {
            "User-Agent": "Mozilla/4.0 (compatible;MSIE 6.0;Windows NT 5.1;SV1;.NET CLR 1.1.4322;.NET CLR 2.0.50727;.NET CLR 3.0.04506.30)"  # noqa: E501
        }

    def translate(self, text):
        text = text[:5000]  # google translate max length
        response = self.session.get(
            self.endpoint,
            params={"tl": self.lang_out, "sl": self.lang_in, "q": text},
            headers=self.headers,
        )
        re_result = re.findall(
            r'(?s)class="(?:t0|result-container)">(.*?)<', response.text
        )
        if response.status_code == 400:
            result = "IRREPARABLE TRANSLATION ERROR"
        else:
            result = html.unescape(re_result[0])
        return remove_control_characters(result)


class TencentTranslator(BaseTranslator):
    # https://github.com/TencentCloud/tencentcloud-sdk-python
    envs = {
        "TENCENTCLOUD_SECRET_ID": None,
        "TENCENTCLOUD_SECRET_KEY": None,
    }

    def __init__(self, service, lang_out, lang_in, model):
        lang_out = "zh" if lang_out == "auto" else lang_out
        lang_in = "en" if lang_in == "auto" else lang_in
        super().__init__(service, lang_out, lang_in, model)
        cred = credential.DefaultCredentialProvider().get_credential()
        self.client = TmtClient(cred, "ap-beijing")
        self.req = TextTranslateRequest()
        self.req.Source = self.lang_in
        self.req.Target = self.lang_out
        self.req.ProjectId = 0

    def translate(self, text):
        self.req.SourceText = text
        resp: TextTranslateResponse = self.client.TextTranslate(self.req)
        return resp.TargetText


class DeepLXTranslator(BaseTranslator):
    # https://deeplx.owo.network/endpoints/free.html
    envs = {
        "DEEPLX_ENDPOINT": "https://api.deepl.com/v2/translate",
    }

    def __init__(self, service, lang_out, lang_in, model):
        lang_out = "zh" if lang_out == "auto" else lang_out
        lang_in = "en" if lang_in == "auto" else lang_in
        super().__init__(service, lang_out, lang_in, model)
        self.endpoint = os.getenv("DEEPLX_ENDPOINT")
        self.session = requests.Session()

    def translate(self, text):
        resp = self.session.post(
            self.endpoint,
            json={
                "source_lang": self.lang_in,
                "target_lang": self.lang_out,
                "text": text,
            },
        )
        return resp.json()["data"]


class DeepLTranslator(BaseTranslator):
    # https://github.com/DeepLcom/deepl-python
    envs = {
        "DEEPL_SERVER_URL": "https://api.deepl.com",
        "DEEPL_AUTH_KEY": None,
    }

    def __init__(self, service, lang_out, lang_in, model):
        lang_out = "zh" if lang_out == "auto" else lang_out
        lang_in = "en" if lang_in == "auto" else lang_in
        super().__init__(service, lang_out, lang_in, model)
        self.session = requests.Session()
        server_url = os.getenv("DEEPL_SERVER_URL")
        auth_key = os.getenv("DEEPL_AUTH_KEY")
        self.client = deepl.Translator(auth_key, server_url=server_url)

    def translate(self, text):
        response = self.client.translate_text(
            text, target_lang=self.lang_out, source_lang=self.lang_in
        )
        return response.text


class OllamaTranslator(BaseTranslator):
    # https://github.com/ollama/ollama-python
    envs = {
        "OLLAMA_HOST": "http://127.0.0.1:11434",
        "OLLAMA_MODEL": "gemma2",
    }

    def __init__(self, service, lang_out, lang_in, model):
        lang_out = "zh-CN" if lang_out == "auto" else lang_out
        lang_in = "en" if lang_in == "auto" else lang_in
        if not model:
            model = os.getenv("OLLAMA_MODEL", self.envs["OLLAMA_MODEL"])
        super().__init__(service, lang_out, lang_in, model)
        self.options = {"temperature": 0}  # 随机采样可能会打断公式标记
        self.client = ollama.Client()

    def translate(self, text):
        response = self.client.chat(
            model=self.model,
            options=self.options,
            messages=self.prompt(text),
        )
        return response["message"]["content"].strip()


class OpenAITranslator(BaseTranslator):
    # https://github.com/openai/openai-python
    envs = {
        "OPENAI_BASE_URL": "https://api.openai.com/v1",
        "OPENAI_API_KEY": None,
        "OPENAI_MODEL": "gpt-4o",
    }

    def __init__(self, service, lang_out, lang_in, model):
        lang_out = "zh-CN" if lang_out == "auto" else lang_out
        lang_in = "en" if lang_in == "auto" else lang_in
        if not model:
            model = os.getenv("OPENAI_MODEL", self.envs["OPENAI_MODEL"])
        super().__init__(service, lang_out, lang_in, model)
        self.options = {"temperature": 0}  # 随机采样可能会打断公式标记
        self.client = openai.OpenAI()

    def translate(self, text) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            **self.options,
            messages=self.prompt(text),
        )
        return response.choices[0].message.content.strip()


class AzureTranslator(BaseTranslator):
    # https://github.com/Azure/azure-sdk-for-python
    envs = {
        "AZURE_ENDPOINT": "https://api.translator.azure.cn",
        "AZURE_APIKEY": None,
    }

    def __init__(self, service, lang_out, lang_in, model):
        lang_out = "zh-Hans" if lang_out == "auto" else lang_out
        lang_in = "en" if lang_in == "auto" else lang_in
        super().__init__(service, lang_out, lang_in, model)
        endpoint = os.environ["AZURE_ENDPOINT"]
        api_key = os.environ["AZURE_APIKEY"]
        credential = AzureKeyCredential(api_key)
        self.client = TextTranslationClient(
            endpoint=endpoint, credential=credential, region="chinaeast2"
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
