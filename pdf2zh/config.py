import enum
import logging
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

log = logging.getLogger(__name__)


class WatermarkOutputMode(enum.Enum):
    """Watermark output mode for PDF files"""

    Watermarked = "watermarked"  # Add watermark to translated PDF
    NoWatermark = "no_watermark"  # Don't add watermark
    Both = "both"  # Output both watermarked and non-watermarked versions


class BasicSettings(BaseSettings):
    """Basic application settings"""

    input_files: set[str] = Field(
        default=set(), description="Input PDF files to process"
    )
    debug: bool = Field(default=False, description="Enable debug mode")
    warmup: bool = Field(
        default=False, description="Only download and verify required assets then exit"
    )
    rpc_doclayout: str | None = Field(
        default=None,
        description="RPC service host address for document layout analysis",
    )
    generate_offline_assets: str | None = Field(
        default=None,
        description="Generate offline assets package in the specified directory",
    )
    restore_offline_assets: str | None = Field(
        default=None,
        description="Restore offline assets package from the specified file",
    )


class TranslationSettings(BaseSettings):
    """Translation related settings"""

    pages: str | None = Field(
        default=None, description="Pages to translate (e.g. '1,2,1-,-3,3-5')"
    )
    min_text_length: int = Field(
        default=5, description="Minimum text length to translate"
    )
    lang_in: str = Field(default="en", description="Source language code")
    lang_out: str = Field(default="zh", description="Target language code")
    output: str | None = Field(
        default=None, description="Output directory for translated files"
    )
    qps: int = Field(default=4, description="QPS limit for translation service")
    ignore_cache: bool = Field(default=False, description="Ignore translation cache")


class PDFSettings(BaseSettings):
    """PDF processing settings"""

    no_dual: bool = Field(
        default=False, description="Do not output bilingual PDF files"
    )
    no_mono: bool = Field(
        default=False, description="Do not output monolingual PDF files"
    )
    formular_font_pattern: str | None = Field(
        default=None, description="Font pattern to identify formula text"
    )
    formular_char_pattern: str | None = Field(
        default=None, description="Character pattern to identify formula text"
    )
    split_short_lines: bool = Field(
        default=False, description="Force split short lines into different paragraphs"
    )
    short_line_split_factor: float = Field(
        default=0.8, description="Split threshold factor for short lines"
    )
    skip_clean: bool = Field(default=False, description="Skip PDF cleaning step")
    dual_translate_first: bool = Field(
        default=False, description="Put translated pages first in dual PDF mode"
    )
    disable_rich_text_translate: bool = Field(
        default=False, description="Disable rich text translation"
    )
    enhance_compatibility: bool = Field(
        default=False, description="Enable all compatibility enhancement options"
    )
    use_alternating_pages_dual: bool = Field(
        default=False, description="Use alternating pages mode for dual PDF"
    )
    watermark_output_mode: WatermarkOutputMode = Field(
        default=WatermarkOutputMode.Watermarked,
        description="Watermark output mode for PDF files",
    )
    max_pages_per_part: int | None = Field(
        default=None, description="Maximum pages per part for split translation"
    )
    no_watermark: bool = Field(
        default=False, description="[DEPRECATED] Do not add watermark to translated PDF"
    )
    translate_table_text: bool = Field(
        default=False, description="Translate table text (experimental)"
    )


class OpenAISettings(BaseSettings):
    """OpenAI API settings"""

    openai: bool = Field(default=False, description="Use OpenAI for translation")
    openai_model: str = Field(default="gpt-4o-mini", description="OpenAI model to use")
    openai_base_url: str | None = Field(
        default=None, description="Base URL for OpenAI API"
    )
    openai_api_key: str | None = Field(
        default=None, description="API key for OpenAI service"
    )


class Settings(BaseSettings):
    """Main settings class that combines all sub-settings"""

    basic: BasicSettings = Field(default_factory=BasicSettings)
    translation: TranslationSettings = Field(default_factory=TranslationSettings)
    pdf: PDFSettings = Field(default_factory=PDFSettings)
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    report_interval: float = Field(
        default=0.1, description="Progress report interval in seconds"
    )

    model_config = SettingsConfigDict(
        env_prefix="PDF2ZH_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        use_enum_values=True,
        validate_default=True,
        extra="ignore",
        cli_parse_args=True,
        cli_avoid_json=True,
        cli_hide_none_type=True,
        cli_prog_name="pdf2zh",
        cli_implicit_flags=True,
        cli_ignore_unknown_args=True,
        cli_kebab_case=True,
    )

    def get_output_dir(self) -> Path:
        """Get output directory, create if not exists"""
        if self.translation.output:
            output_dir = Path(self.translation.output)
        else:
            output_dir = Path.cwd()

        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def validate_settings(self) -> None:
        """Validate settings"""
        # Validate translation service selection
        if not self.openai.openai:
            raise ValueError("Must select a translation service: --openai")

        # Validate OpenAI parameters
        if self.openai.openai and not self.openai.openai_api_key:
            raise ValueError("OpenAI API key is required when using OpenAI service")

        # Validate files
        for file in self.basic.input_files:
            file_path = Path(file.strip("\"'"))
            if not file_path.exists():
                raise ValueError(f"File does not exist: {file}")
            if not file_path.suffix.lower() == ".pdf":
                raise ValueError(f"File is not a PDF file: {file}")

    def parse_pages(self) -> list[tuple[int, int]] | None:
        """Parse pages string into list of page ranges"""
        if not self.translation.pages:
            return None

        ranges: list[tuple[int, int]] = []
        for part in self.translation.pages.split(","):
            part = part.strip()
            if "-" in part:
                start, end = part.split("-")
                start_as_int = int(start) if start else 1
                end_as_int = int(end) if end else -1
                ranges.append((start_as_int, end_as_int))
            else:
                page = int(part)
                ranges.append((page, page))
        return ranges


class ConfigManager:
    """Singleton configuration manager"""

    _instance: Optional["ConfigManager"] = None
    _settings: Settings | None = None

    def __new__(cls) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def settings(self) -> Settings:
        if self._settings is None:
            self._settings = Settings()
            self._settings.validate_settings()
        return self._settings

    def reload(self) -> None:
        """Reload settings"""
        self._settings = Settings()
        self._settings.validate_settings()


ConfigManager().settings.model_dump()
