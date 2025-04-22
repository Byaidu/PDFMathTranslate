from __future__ import annotations

import logging

from pydantic import BaseModel
from pydantic import Field
from pydantic import create_model

from pdf2zh.config.model import BasicSettings
from pdf2zh.config.model import PDFSettings
from pdf2zh.config.model import SettingsModel
from pdf2zh.config.model import TranslationSettings
from pdf2zh.config.translate_engine_model import _DEFAULT_TRANSLATION_ENGINE
from pdf2zh.config.translate_engine_model import TRANSLATION_ENGINE_METADATA

logger = logging.getLogger(__name__)


__translation_flag_fields = {
    x.cli_flag_name: (
        bool,
        Field(
            default=False, description=f"Use {x.translate_engine_type} for translation"
        ),
    )
    for x in TRANSLATION_ENGINE_METADATA
}

__translation_flag_fields.update(
    {
        x.cli_detail_field_name: (
            x.setting_model_type,
            Field(default_factory=x.setting_model_type),
        )
        for x in TRANSLATION_ENGINE_METADATA
        if x.cli_detail_field_name
    }
)

__exclude_fields = list(__translation_flag_fields.keys())


class CLIEnvBaseSettingsModel(BaseModel):
    """Main settings class that combines all sub-settings"""

    config_file: str | None = Field(
        default=None, description="Path to the configuration file"
    )
    report_interval: float = Field(
        default=0.1, description="Progress report interval in seconds"
    )
    basic: BasicSettings = Field(default_factory=BasicSettings)
    translation: TranslationSettings = Field(default_factory=TranslationSettings)
    pdf: PDFSettings = Field(default_factory=PDFSettings)


CLIEnvSettingsModel = create_model(
    "CLIEnvSettingsModel",
    __base__=CLIEnvBaseSettingsModel,
    **__translation_flag_fields,
)


def to_settings_model(self) -> SettingsModel:
    for metadata in TRANSLATION_ENGINE_METADATA:
        if getattr(self, metadata.cli_flag_name):
            if metadata.cli_detail_field_name:
                translate_engine_settings = metadata.setting_model_type(
                    **getattr(self, metadata.cli_detail_field_name).model_dump()
                )
            else:
                translate_engine_settings = metadata.setting_model_type()
            break
    else:
        logger.warning("No translation engine selected, using Bing")
        translate_engine_settings = _DEFAULT_TRANSLATION_ENGINE()

    return SettingsModel(
        **self.model_dump(exclude=__exclude_fields),
        translate_engine_settings=translate_engine_settings,
    )


def validate_settings(self) -> None:
    self.to_settings_model().validate_settings()


def clone(self):
    return self.model_copy(deep=True)


CLIEnvSettingsModel.to_settings_model = to_settings_model
CLIEnvSettingsModel.validate_settings = validate_settings
CLIEnvSettingsModel.clone = clone
