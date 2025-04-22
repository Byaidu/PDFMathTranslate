import re
import typing
from dataclasses import dataclass
from typing import Literal
from typing import TypeAlias

from pydantic import BaseModel
from pydantic import Field


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


# 所有翻译引擎
TRANSLATION_ENGINE_SETTING_TYPE: TypeAlias = (
    OpenAISettings | GoogleSettings | BingSettings
)

# 默认翻译引擎
_DEFAULT_TRANSLATION_ENGINE = BingSettings

assert len(_DEFAULT_TRANSLATION_ENGINE.model_fields) == 1, (
    "Default translation engine cannot have detail settings"
)

# The following is magic code.
# If you need to make changes, please contact the maintainer.


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
