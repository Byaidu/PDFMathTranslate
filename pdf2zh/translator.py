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
    name = "base"
    envs = {}
    lang_map = {}

    def __init__(self, service, lang_out: str, lang_in: str, model):
        lang_out = self.lang_map.get(lang_out.lower(), lang_out)
        lang_in = self.lang_map.get(lang_in.lower(), lang_in)
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
    name = "google"
    lang_map = {"zh": "zh-CN"}

    def __init__(self, service, lang_out, lang_in, model):
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


class BingTranslator(BaseTranslator):
    # https://github.com/immersive-translate/old-immersive-translate/blob/6df13da22664bea2f51efe5db64c63aca59c4e79/src/background/translationService.js
    # TODO: IID & IG
    name = "bing"
    lang_map = {"zh": "zh-Hans"}

    def __init__(self, service, lang_out, lang_in, model):
        super().__init__(service, lang_out, lang_in, model)
        self.session = requests.Session()
        self.endpoint = "https://www.bing.com/ttranslatev3"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",  # noqa: E501
        }

    def fineSID(self):
        resp = self.session.get("https://www.bing.com/translator")
        ig = re.findall(r"\"ig\":\"(.*?)\"", resp.text)[0]
        iid = re.findall(r"data-iid=\"(.*?)\"", resp.text)[-1]
        key, token = re.findall(
            r"params_AbusePreventionHelper\s=\s\[(.*?),\"(.*?)\",", resp.text
        )[0]
        return ig, iid, key, token

    def translate(self, text):
        text = text[:1000]  # bing translate max length
        ig, iid, key, token = self.fineSID()
        resp = self.session.post(
            f"{self.endpoint}?IG={ig}&IID={iid}",
            data={
                "fromLang": self.lang_in,
                "to": self.lang_out,
                "text": text,
                "token": token,
                "key": key,
            },
            headers=self.headers,
        )
        return resp.json()[0]["translations"][0]["text"]


class DeepLTranslator(BaseTranslator):
    # https://github.com/DeepLcom/deepl-python
    name = "deepl"
    envs = {
        "DEEPL_SERVER_URL": "https://api.deepl.com",
        "DEEPL_AUTH_KEY": None,
    }
    lang_map = {"zh": "zh-Hans"}

    def __init__(self, service, lang_out, lang_in, model):
        super().__init__(service, lang_out, lang_in, model)
        self.session = requests.Session()
        server_url = os.getenv("DEEPL_SERVER_URL", self.envs["DEEPL_SERVER_URL"])
        auth_key = os.getenv("DEEPL_AUTH_KEY")
        self.client = deepl.Translator(auth_key, server_url=server_url)

    def translate(self, text):
        response = self.client.translate_text(
            text, target_lang=self.lang_out, source_lang=self.lang_in
        )
        return response.text


class DeepLXTranslator(BaseTranslator):
    # https://deeplx.owo.network/endpoints/free.html
    name = "deeplx"
    envs = {
        "DEEPLX_ENDPOINT": "https://api.deepl.com/translate",
    }
    lang_map = {"zh": "zh-Hans"}

    def __init__(self, service, lang_out, lang_in, model):
        super().__init__(service, lang_out, lang_in, model)
        self.endpoint = os.getenv("DEEPLX_ENDPOINT", self.envs["DEEPLX_ENDPOINT"])
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


class OllamaTranslator(BaseTranslator):
    # https://github.com/ollama/ollama-python
    name = "ollama"
    envs = {
        "OLLAMA_HOST": "http://127.0.0.1:11434",
        "OLLAMA_MODEL": "gemma2",
    }

    def __init__(self, service, lang_out, lang_in, model):
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
    name = "openai"
    envs = {
        "OPENAI_BASE_URL": "https://api.openai.com/v1",
        "OPENAI_API_KEY": None,
        "OPENAI_MODEL": "gpt-4o-mini",
    }

    def __init__(self, service, lang_out, lang_in, model, base_url=None, api_key=None):
        if not model:
            model = os.getenv("OPENAI_MODEL", self.envs["OPENAI_MODEL"])
        super().__init__(service, lang_out, lang_in, model)
        self.options = {"temperature": 0}  # 随机采样可能会打断公式标记
        self.client = openai.OpenAI(base_url=base_url, api_key=api_key)

    def translate(self, text) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            **self.options,
            messages=self.prompt(text),
        )
        return response.choices[0].message.content.strip()


class ZhipuTranslator(OpenAITranslator):
    # https://bigmodel.cn/dev/api/thirdparty-frame/openai-sdk
    name = "zhipu"
    envs = {
        "ZHIPU_API_KEY": None,
        "ZHIPU_MODEL": "glm-4-flash",
    }

    def __init__(self, service, lang_out, lang_in, model):
        base_url = "https://open.bigmodel.cn/api/paas/v4"
        api_key = os.getenv("ZHIPU_API_KEY")
        if not model:
            model = os.getenv("ZHIPU_MODEL", self.envs["ZHIPU_MODEL"])
        super().__init__(
            service, lang_out, lang_in, model, base_url=base_url, api_key=api_key
        )


class SiliconTranslator(OpenAITranslator):
    # https://docs.siliconflow.cn/quickstart
    name = "silicon"
    envs = {
        "SILICON_API_KEY": None,
        "SILICON_MODEL": "Qwen/Qwen2.5-7B-Instruct",
    }

    def __init__(self, service, lang_out, lang_in, model):
        base_url = "https://api.siliconflow.cn/v1"
        api_key = os.getenv("SILICON_API_KEY")
        if not model:
            model = os.getenv("SILICON_MODEL", self.envs["SILICON_MODEL"])
        super().__init__(
            service, lang_out, lang_in, model, base_url=base_url, api_key=api_key
        )


class AzureTranslator(BaseTranslator):
    # https://github.com/Azure/azure-sdk-for-python
    name = "azure"
    envs = {
        "AZURE_ENDPOINT": "https://api.translator.azure.cn",
        "AZURE_API_KEY": None,
    }
    lang_map = {"zh": "zh-Hans"}

    def __init__(self, service, lang_out, lang_in, model):
        super().__init__(service, lang_out, lang_in, model)
        endpoint = os.getenv("AZURE_ENDPOINT", self.envs["AZURE_ENDPOINT"])
        api_key = os.getenv("AZURE_API_KEY")
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


class TencentTranslator(BaseTranslator):
    # https://github.com/TencentCloud/tencentcloud-sdk-python
    name = "tencent"
    envs = {
        "TENCENTCLOUD_SECRET_ID": None,
        "TENCENTCLOUD_SECRET_KEY": None,
    }

    def __init__(self, service, lang_out, lang_in, model):
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
