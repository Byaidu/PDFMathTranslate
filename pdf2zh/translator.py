import html
import json
import re
from os import getenv

import ollama
import requests


class BaseTranslator:
    def __init__(self,service,lang_out,lang_in):
        self.service=service
        self.lang_out=lang_out
        self.lang_in=lang_in

    def translate(self,text):
        pass

    def __str__(self):
        pass

    def __str__(self):
        return f'{self.service} {self.lang_out} {self.lang_in}'

class GoogleTranslator(BaseTranslator):
    def __init__(self,service,lang_out,lang_in):
        super().__init__(service,lang_out,lang_in)
        self.session=requests.Session()
        self.base_link="http://translate.google.com/m"
        self.headers={'User-Agent':'Mozilla/4.0 (compatible;MSIE 6.0;Windows NT 5.1;SV1;.NET CLR 1.1.4322;.NET CLR 2.0.50727;.NET CLR 3.0.04506.30)'}

    def translate(self,text):
        text=text[:5000] # Max Length
        response=self.session.get(self.base_link,params={'tl':self.lang_out,'sl':self.lang_in,'q':text},headers=self.headers)
        re_result=re.findall(r'(?s)class="(?:t0|result-container)">(.*?)<',response.text)
        if len(re_result) == 0:
            raise ValueError('Empty translation result')
        else:
            result=html.unescape(re_result[0])
        return result


class DeepLXTranslator(BaseTranslator):
    def __init__(
        self,
        service,
        lang_out,
        lang_in,
    ):
        super().__init__(service, lang_out, lang_in)
        self.session = requests.Session()
        self.base_link = ""
        self.model = service
        self.headers = {
            "Content-Type": "application/json; charset=utf-8",
        }

    def translate(self, text):
        text = text[:5000]  # Max Length
        if getenv("DEEPLX_TOKEN"):
            DEEPLX_TOKEN = getenv("DEEPLX_TOKEN")
        else:
            DEEPLX_TOKEN = ""
        if DEEPLX_TOKEN == "":
            raise ValueError("No valid env `DEEPLX_TOKEN`")
        self.base_link = f"https://api.deeplx.org/{DEEPLX_TOKEN}/translate"

        response = self.session.post(
            self.base_link,
            json.dumps(
                {
                    "target_lang": "zh",
                    # "source_lang": self.lang_in,
                    "text": text,
                }
            ),
            headers=self.headers,
        )
        # re_result = re.findall(
        #     r'(?s)class="(?:t0|result-container)">(.*?)<', response.text
        # )
        if response.status_code == 200:
            result = json.loads(response.text)
        else:
            raise ValueError("HTTP Error")
        try:
            result = result["data"]
            return "Deepl" + result
        except KeyError:
            result = ""
            raise ValueError("No valid key in DeepLX's response")
        # if len(result) == 0:
        #     raise ValueError("Empty translation result")
        # else:
        #     result = html.unescape(result[0])
        # return result


class OllamaTranslator(BaseTranslator):
    def __init__(self,service,lang_out,lang_in):
        super().__init__(service,lang_out,lang_in)
        self.model=service
        self.options={'temperature':0} # 随机采样可能会打断公式标记

    def translate(self,text):
        result=ollama.chat(model=self.model,options=self.options,messages=[
            {
                'role': 'system',
                'content': 'You are a professional,authentic machine translation engine.',
            },
            { 'role': 'user','content': f'Translate the following markdown source text to {self.lang_out}. Keep the formula notation $v*$ unchanged. Output translation directly without any additional text.\nSource Text: {text}\nTranslated Text:' }
        ])['message']['content'].strip()
        return result