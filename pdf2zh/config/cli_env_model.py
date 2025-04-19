import logging

from pydantic import BaseModel
from pydantic import Field

from pdf2zh.config.model import BasicSettings
from pdf2zh.config.model import BingSettings
from pdf2zh.config.model import GoogleSettings
from pdf2zh.config.model import OpenAISettings
from pdf2zh.config.model import PDFSettings
from pdf2zh.config.model import SettingsModel
from pdf2zh.config.model import TranslationSettings

logger = logging.getLogger(__name__)


class CLIEnvSettingsModel(BaseModel):
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

    openai_detail: OpenAISettings = Field(default_factory=OpenAISettings)
    openai: bool = Field(default=False, description="Use OpenAI for translation")
    google: bool = Field(default=False, description="Use Google for translation")
    bing: bool = Field(default=False, description="Use Bing for translation")

    def to_settings_model(self) -> SettingsModel:
        if self.openai:
            translate_engine_settings = OpenAISettings(
                **self.openai_detail.model_dump()
            )
        elif self.google:
            translate_engine_settings = GoogleSettings()
        elif self.bing:
            translate_engine_settings = BingSettings()
        else:
            logger.warning("No translation engine selected, using Bing")
            translate_engine_settings = BingSettings()

        return SettingsModel(
            **self.model_dump(exclude={"openai_detail", "openai", "google", "bing"}),
            translate_engine_settings=translate_engine_settings,
        )

    def validate_settings(self) -> None:
        self.to_settings_model().validate_settings()
