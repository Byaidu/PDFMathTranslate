import re
import typing
from dataclasses import dataclass
from types import NoneType
from typing import Literal
from typing import TypeAlias

from pydantic import BaseModel
from pydantic import Field

# any field in SENSITIVE_FIELDS will be masked in GUI
GUI_SENSITIVE_FIELDS = []
# any field in GUI_PASSWORD_FIELDS will be masked in GUI and treated as password
GUI_PASSWORD_FIELDS = []


class TranslateEngineSettingError(Exception):
    """Translate engine setting error"""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


## Please add the translator configuration class below this location.

# Please note that all translator configurations must be of string type,
# otherwise the GUI will not function properly!
#
# You should implement validation of the translator configuration in validate_settings.
# And complete type conversion (if any) in the corresponding implementation of the translator.


class OpenAISettings(BaseModel):
    """OpenAI API settings"""

    translate_engine_type: Literal["OpenAI"] = Field(default="OpenAI")

    openai_model: str = Field(default="gpt-4o-mini", description="OpenAI model to use")
    openai_base_url: str | None = Field(
        default=None, description="Base URL for OpenAI API"
    )
    openai_api_key: str | None = Field(
        default=None, description="API key for OpenAI service"
    )

    def validate_settings(self) -> None:
        if not self.openai_api_key:
            raise ValueError("OpenAI API key is required")
        if self.openai_base_url:
            self.openai_base_url = re.sub(
                "/chat/completions/?$", "", self.openai_base_url
            )


GUI_PASSWORD_FIELDS.append("openai_api_key")
GUI_SENSITIVE_FIELDS.append("openai_base_url")


class BingSettings(BaseModel):
    """Bing Translation settings"""

    translate_engine_type: Literal["Bing"] = Field(default="Bing")

    def validate_settings(self) -> None:
        pass


class GoogleSettings(BaseModel):
    """Google Translation settings"""

    translate_engine_type: Literal["Google"] = Field(default="Google")

    def validate_settings(self) -> None:
        pass


class DeepLSettings(BaseModel):
    """Bing Translation settings"""

    translate_engine_type: Literal["DeepL"] = Field(default="DeepL")
    deepl_auth_key: str | None = Field(default=None, description="DeepL auth key")

    def validate_settings(self) -> None:
        if not self.deepl_auth_key:
            raise ValueError("DeepL Auth key is required")


GUI_PASSWORD_FIELDS.append("deepl_auth_key")

# for openai compatibility translator
# You only need to add the corresponding configuration class
# and return the OpenAISettings instance using the transform method.


class DeepSeekSettings(BaseModel):
    """DeepSeek settings"""

    translate_engine_type: Literal["DeepSeek"] = Field(default="DeepSeek")

    deepseek_model: str = Field(
        default="deepseek-chat", description="DeepSeek model to use"
    )
    deepseek_api_key: str | None = Field(
        default=None, description="API key for DeepSeek service"
    )

    def validate_settings(self) -> None:
        if not self.deepseek_api_key:
            raise ValueError("DeepSeek API key is required")

    def transform(self) -> OpenAISettings:
        return OpenAISettings(
            openai_model=self.deepseek_model,
            openai_api_key=self.deepseek_api_key,
            openai_base_url="https://api.deepseek.com/v1",
        )


GUI_PASSWORD_FIELDS.append("deepseek_api_key")


class OllamaSettings(BaseModel):
    """Ollama API settings"""

    translate_engine_type: Literal["Ollama"] = Field(default="Ollama")

    ollama_model: str = Field(default="gemma2", description="Ollama model to use")
    ollama_host: str | None = Field(
        default="http://localhost:11434", description="Ollama host"
    )
    num_predict: int | None = Field(
        default=2000, description="The max number of token to predict."
    )

    def validate_settings(self) -> None:
        if not self.ollama_host:
            raise ValueError("Ollama host is required")


class XinferenceSettings(BaseModel):
    """Xinference API settings"""

    translate_engine_type: Literal["Xinference"] = Field(default="Xinference")

    xinference_model: str = Field(
        default="gemma-2-it", description="Xinference model to use"
    )
    xinference_host: str | None = Field(default=None, description="Xinference host")

    def validate_settings(self) -> None:
        if not self.xinference_host:
            raise ValueError("Xinference host is required")


class AzureOpenAISettings(BaseModel):
    """AzureOpenAI API settings"""

    translate_engine_type: Literal["AzureOpenAI"] = Field(default="AzureOpenAI")

    azure_openai_model: str = Field(
        default="gpt-4o-mini", description="AzureOpenAI model to use"
    )
    azure_openai_base_url: str | None = Field(
        default=None, description="Base URL for AzureOpenAI API"
    )
    azure_openai_api_key: str | None = Field(
        default=None, description="API key for AzureOpenAI service"
    )
    azure_openai_api_version: str = Field(
        default="2024-06-01", description="API version for AzureOpenAI service"
    )

    def validate_settings(self) -> None:
        if not self.azure_openai_api_key:
            raise ValueError("AzureOpenAI API key is required")


GUI_PASSWORD_FIELDS.append("azure_openai_api_key")


class ModelScopeSettings(BaseModel):
    """ModelScope API settings"""

    translate_engine_type: Literal["ModelScope"] = Field(default="ModelScope")

    modelscope_model: str = Field(
        default="Qwen/Qwen2.5-32B-Instruct", description="ModelScope model to use"
    )
    modelscope_api_key: str | None = Field(
        default=None, description="API key for ModelScope service"
    )

    def validate_settings(self) -> None:
        if not self.modelscope_api_key:
            raise ValueError("ModelScope API key is required")

    def transform(self) -> OpenAISettings:
        return OpenAISettings(
            openai_model=self.modelscope_model,
            openai_api_key=self.modelscope_api_key,
            openai_base_url="https://api-inference.modelscope.cn/v1",
        )


GUI_PASSWORD_FIELDS.append("modelscope_api_key")


class ZhipuSettings(BaseModel):
    """Zhipu API settings"""

    translate_engine_type: Literal["Zhipu"] = Field(default="Zhipu")

    zhipu_model: str = Field(default="glm-4-flash", description="Zhipu model to use")
    zhipu_api_key: str | None = Field(
        default=None, description="API key for Zhipu service"
    )

    def validate_settings(self) -> None:
        if not self.zhipu_api_key:
            raise ValueError("Zhipu API key is required")

    def transform(self) -> OpenAISettings:
        return OpenAISettings(
            openai_model=self.zhipu_model,
            openai_api_key=self.zhipu_api_key,
            openai_base_url="https://open.bigmodel.cn/api/paas/v4",
        )


GUI_PASSWORD_FIELDS.append("zhipu_api_key")


class SiliconFlowSettings(BaseModel):
    """SiliconFlow API settings"""

    translate_engine_type: Literal["SiliconFlow"] = Field(default="SiliconFlow")

    siliconflow_base_url: str | None = Field(
        default="https://api.siliconflow.cn/v1",
        description="Base URL for SiliconFlow API",
    )
    siliconflow_model: str = Field(
        default="Qwen/Qwen2.5-7B-Instruct", description="SiliconFlow model to use"
    )
    siliconflow_api_key: str | None = Field(
        default=None, description="API key for SiliconFlow service"
    )
    siliconflow_enable_thinking: bool | None = Field(
        default=False, description="Enable thinking for SiliconFlow service"
    )

    def validate_settings(self) -> None:
        if not self.siliconflow_api_key:
            raise ValueError("SiliconFlow API key is required")


GUI_PASSWORD_FIELDS.append("siliconflow_api_key")


class TencentSettings(BaseModel):
    """Tencent Mechine Translation settings"""

    translate_engine_type: Literal["TencentMechineTranslation"] = Field(
        default="TencentMechineTranslation"
    )
    tencentcloud_secret_id: str | None = Field(
        default=None, description="Tencent Mechine Translation secret ID"
    )
    tencentcloud_secret_key: str | None = Field(
        default=None, description="Tencent Mechine Translation secret Key"
    )

    def validate_settings(self) -> None:
        if not self.tencentcloud_secret_id:
            raise ValueError("Tencent Mechine Translation ID is required")
        if not self.tencentcloud_secret_key:
            raise ValueError("Tencent Mechine Translation Key is required")


GUI_PASSWORD_FIELDS.append("tencentcloud_secret_id")
GUI_PASSWORD_FIELDS.append("tencentcloud_secret_key")


class GeminiSettings(BaseModel):
    """Gemini API settings"""

    translate_engine_type: Literal["Gemini"] = Field(default="Gemini")

    gemini_model: str = Field(
        default="gemini-1.5-flash", description="Gemini model to use"
    )
    gemini_api_key: str | None = Field(
        default=None, description="API key for Gemini service"
    )

    def validate_settings(self) -> None:
        if not self.gemini_api_key:
            raise ValueError("Gemini API key is required")

    def transform(self) -> OpenAISettings:
        return OpenAISettings(
            openai_model=self.gemini_model,
            openai_api_key=self.gemini_api_key,
            openai_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )


GUI_PASSWORD_FIELDS.append("gemini_api_key")


class AzureSettings(BaseModel):
    """Azure Translation settings"""

    translate_engine_type: Literal["Azure"] = Field(default="Azure")
    azure_endpoint: str | None = Field(
        default="https://api.translator.azure.cn", description="Azure endpoint"
    )
    azure_api_key: str | None = Field(default=None, description="Azure API Key")

    def validate_settings(self) -> None:
        if not self.azure_api_key:
            raise ValueError("Tencent Mechine Translation ID is required")


GUI_PASSWORD_FIELDS.append("azure_api_key")


class AnythingLLMSettings(BaseModel):
    """AnythingLLM settings"""

    translate_engine_type: Literal["AnythingLLM"] = Field(default="AnythingLLM")
    anythingllm_url: str | None = Field(default=None, description="AnythingLLM url")
    anythingllm_apikey: str | None = Field(
        default=None, description="AnythingLLM API Key"
    )

    def validate_settings(self) -> None:
        if not self.anythingllm_apikey:
            raise ValueError("AnythingLLM API Key is required")


GUI_PASSWORD_FIELDS.append("anythingllm_apikey")


class DifySettings(BaseModel):
    """Dify settings"""

    translate_engine_type: Literal["Dify"] = Field(default="Dify")
    dify_url: str | None = Field(default=None, description="Dify url")
    dify_apikey: str | None = Field(default=None, description="Dify API Key")

    def validate_settings(self) -> None:
        if not self.dify_apikey:
            raise ValueError("Dify API Key is required")


GUI_PASSWORD_FIELDS.append("dify_apikey")


class GrokSettings(BaseModel):
    """Grok API settings"""

    translate_engine_type: Literal["Grok"] = Field(default="Grok")

    grok_model: str = Field(default="grok-2-1212", description="Grok model to use")
    grok_api_key: str | None = Field(
        default=None, description="API key for Grok service"
    )

    def validate_settings(self) -> None:
        if not self.grok_api_key:
            raise ValueError("Grok API key is required")

    def transform(self) -> OpenAISettings:
        return OpenAISettings(
            openai_model=self.grok_model,
            openai_api_key=self.grok_api_key,
            openai_base_url="https://api.x.ai/v1",
        )


GUI_PASSWORD_FIELDS.append("grok_api_key")


class GroqSettings(BaseModel):
    """Groq API settings"""

    translate_engine_type: Literal["Groq"] = Field(default="Groq")

    groq_model: str = Field(
        default="llama-3-3-70b-versatile", description="Groq model to use"
    )
    groq_api_key: str | None = Field(
        default=None, description="API key for Groq service"
    )

    def validate_settings(self) -> None:
        if not self.groq_api_key:
            raise ValueError("Groq API key is required")

    def transform(self) -> OpenAISettings:
        return OpenAISettings(
            openai_model=self.groq_model,
            openai_api_key=self.groq_api_key,
            openai_base_url="https://api.groq.com/openai/v1",
        )


GUI_PASSWORD_FIELDS.append("groq_api_key")


class QwenMtSettings(BaseModel):
    """QwenMt API settings"""

    translate_engine_type: Literal["QwenMt"] = Field(default="QwenMt")

    qwenmt_model: str = Field(
        default="qwen-mt-turbo", description="QwenMt model to use"
    )
    qwenmt_base_url: str | None = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        description="Base URL for QwenMt API",
    )
    qwenmt_api_key: str | None = Field(
        default=None, description="API key for QwenMt service"
    )
    ali_domains: str | None = Field(
        default="This sentence is extracted from a scientific paper. When translating, please pay close attention to the use of specialized troubleshooting terminologies and adhere to scientific sentence structures to maintain the technical rigor and precision of the original text.",
        description="ALI_DOMAIN for QwenMt service",
    )

    def validate_settings(self) -> None:
        if not self.qwenmt_api_key:
            raise ValueError("OpenAI API key is required")


GUI_PASSWORD_FIELDS.append("qwenmt_api_key")


class OpenAICompatibleSettings(BaseModel):
    """OpenAICompatible settings"""

    translate_engine_type: Literal["OpenAICompatible"] = Field(
        default="OpenAICompatible"
    )

    openai_compatible_model: str = Field(
        default="gpt-4o-mini", description="OpenAI Compatible model to use"
    )
    openai_compatible_base_url: str | None = Field(
        default=None, description="Base URL for OpenAI Compatible service"
    )
    openai_compatible_api_key: str | None = Field(
        default=None, description="API key for OpenAI Compatible service"
    )

    def validate_settings(self) -> None:
        if not self.openai_compatible_api_key:
            raise ValueError("OpenAI Compatible API key is required")
        if not self.openai_compatible_base_url:
            raise ValueError("OpenAI Compatible base URL is required")
        if not self.openai_compatible_model:
            raise ValueError("OpenAI Compatible model is required")

    def transform(self) -> OpenAISettings:
        return OpenAISettings(
            openai_model=self.openai_compatible_model,
            openai_api_key=self.openai_compatible_api_key,
            openai_base_url=self.openai_compatible_base_url,
        )


GUI_PASSWORD_FIELDS.append("openai_compatible_api_key")


## Please add the translator configuration class above this location.

# 所有翻译引擎
TRANSLATION_ENGINE_SETTING_TYPE: TypeAlias = (
    OpenAISettings
    | GoogleSettings
    | BingSettings
    | DeepLSettings
    | DeepSeekSettings
    | OllamaSettings
    | XinferenceSettings
    | AzureOpenAISettings
    | ModelScopeSettings
    | ZhipuSettings
    | SiliconFlowSettings
    | TencentSettings
    | GeminiSettings
    | AzureSettings
    | AnythingLLMSettings
    | DifySettings
    | GrokSettings
    | GroqSettings
    | QwenMtSettings
    | OpenAICompatibleSettings
)

# 不支持的翻译引擎
NOT_SUPPORTED_TRANSLATION_ENGINE_SETTING_TYPE: TypeAlias = NoneType

# 默认翻译引擎
_DEFAULT_TRANSLATION_ENGINE = BingSettings

assert len(_DEFAULT_TRANSLATION_ENGINE.model_fields) == 1, (
    "Default translation engine cannot have detail settings"
)

# The following is magic code,
# if you need to modify it,
# please contact the maintainer!

GUI_SENSITIVE_FIELDS.extend(GUI_PASSWORD_FIELDS)


@dataclass
class TranslationEngineMetadata:
    translate_engine_type: str
    cli_flag_name: str
    cli_detail_field_name: str | None
    setting_model_type: type[BaseModel]

    def __init__(
        self,
        setting_model_type: type[BaseModel],
    ) -> None:
        self.translate_engine_type = setting_model_type.model_fields[
            "translate_engine_type"
        ].default
        self.cli_flag_name = self.translate_engine_type.lower()
        self.cli_detail_field_name = self.cli_flag_name + "_detail"
        self.setting_model_type = setting_model_type
        if len(setting_model_type.model_fields) == 1:
            self.cli_detail_field_name = None


args = typing.get_args(TRANSLATION_ENGINE_SETTING_TYPE)

TRANSLATION_ENGINE_METADATA = [
    TranslationEngineMetadata(
        setting_model_type=arg,
    )
    for arg in args
]

TRANSLATION_ENGINE_METADATA_MAP = {
    metadata.translate_engine_type: metadata for metadata in TRANSLATION_ENGINE_METADATA
}


# auto check duplicate translation engine metadata
assert len(TRANSLATION_ENGINE_METADATA_MAP) == len(TRANSLATION_ENGINE_METADATA), (
    "Duplicate translation engine metadata"
)

# auto check duplicate cli flag name and cli detail field name
dedup_set = set()
for metadata in TRANSLATION_ENGINE_METADATA:
    if metadata.cli_flag_name in dedup_set:
        raise ValueError(f"Duplicate cli flag name: {metadata.cli_flag_name}")
    dedup_set.add(metadata.cli_flag_name)
    if metadata.cli_detail_field_name and metadata.cli_detail_field_name in dedup_set:
        raise ValueError(
            f"Duplicate cli detail field name: {metadata.cli_detail_field_name}"
        )
    dedup_set.add(metadata.cli_detail_field_name)
del dedup_set

DEFAULT_TRANSLATION_ENGINE_METADATA = TRANSLATION_ENGINE_METADATA_MAP[
    _DEFAULT_TRANSLATION_ENGINE.model_fields["translate_engine_type"].default
]

if __name__ == "__main__":
    print(TRANSLATION_ENGINE_METADATA_MAP)
