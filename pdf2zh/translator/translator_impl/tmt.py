from pdf2zh.config.model import SettingsModel
from pdf2zh.translator.base_rate_limiter import BaseRateLimiter
from pdf2zh.translator.base_translator import BaseTranslator
from tencentcloud.common import credential
from tencentcloud.tmt.v20180321.models import TextTranslateRequest
from tencentcloud.tmt.v20180321.models import TextTranslateResponse
from tencentcloud.tmt.v20180321.tmt_client import TmtClient


class TencentTranslator(BaseTranslator):
    name = "tencent"

    def __init__(
        self,
        settings: SettingsModel,
        rate_limiter: BaseRateLimiter,
    ):
        super().__init__(settings, rate_limiter)
        try:
            cred = credential.DefaultCredentialProvider().get_credential()
        except OSError:
            cred = credential.Credential(
                settings.translate_engine_settings.tencentcloud_secret_id,
                settings.translate_engine_settings.tencentcloud_secret_key,
            )
        self.client = TmtClient(cred, "ap-beijing")
        self.req = TextTranslateRequest()
        self.req.Source = self.lang_in
        self.req.Target = self.lang_out
        self.req.ProjectId = 0

    def do_translate(self, text, rate_limit_params: dict = None):
        self.req.SourceText = text
        resp: TextTranslateResponse = self.client.TextTranslate(self.req)
        return resp.TargetText
