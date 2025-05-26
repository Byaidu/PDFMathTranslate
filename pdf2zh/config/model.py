from __future__ import annotations

import enum
import logging
import re
from pathlib import Path

from pydantic import BaseModel
from pydantic import Field

from pdf2zh.config.translate_engine_model import TRANSLATION_ENGINE_SETTING_TYPE

log = logging.getLogger(__name__)

# Very Important!
# Only the following fields can be used for Field:
# default
# description
# default_factory
# alias
# discriminator
#
# If you want to use other fields, please go to `pdf2zh/config/cli_env_model.py`
# and add the corresponding forwarding statement at `__cli_env_settings_model_fields`!


class WatermarkOutputMode(enum.Enum):
    """Watermark output mode for PDF files"""

    Watermarked = "watermarked"  # Add watermark to translated PDF
    NoWatermark = "no_watermark"  # Don't add watermark
    Both = "both"  # Output both watermarked and non-watermarked versions


class BasicSettings(BaseModel):
    """Basic application settings"""

    input_files: set[str] = Field(
        default=set(), description="Input PDF files to process"
    )
    debug: bool = Field(default=False, description="Enable debug mode")
    gui: bool = Field(default=False, description="Enable GUI mode")
    warmup: bool = Field(
        default=False, description="Only download and verify required assets then exit"
    )
    generate_offline_assets: str | None = Field(
        default=None,
        description="Generate offline assets package in the specified directory",
    )
    restore_offline_assets: str | None = Field(
        default=None,
        description="Restore offline assets package from the specified file",
    )


class GUISettings(BaseModel):
    """GUI related settings"""

    share: bool = Field(default=False, description="Enable sharing mode")
    auth_file: str | None = Field(
        default=None, description="Path to the authentication file"
    )
    enabled_services: str | None = Field(default=None, description="Enabled services")
    disable_gui_sensitive_input: bool = Field(
        default=False, description="Disable GUI sensitive input"
    )
    disable_config_auto_save: bool = Field(
        default=False, description="Disable automatic saving of configuration"
    )


class TranslationSettings(BaseModel):
    """Translation related settings"""

    min_text_length: int = Field(
        default=5, description="Minimum text length to translate"
    )
    rpc_doclayout: str | None = Field(
        default=None,
        description="RPC service host address for document layout analysis",
    )
    lang_in: str = Field(default="en", description="Source language code")
    lang_out: str = Field(default="zh", description="Target language code")
    output: str | None = Field(
        default=None, description="Output directory for translated files"
    )
    qps: int = Field(default=4, description="QPS limit for translation service")
    ignore_cache: bool = Field(default=False, description="Ignore translation cache")
    custom_system_prompt: str | None = Field(
        default=None,
        description='Custom system prompt for translation. It is mainly used to add the `/no_think` instruction of Qwen 3 in the prompt. e.g. --custom-system-prompt "/no_think You are a professional, authentic machine translation engine."',
    )


class PDFSettings(BaseModel):
    """PDF processing settings"""

    pages: str | None = Field(
        default=None, description="Pages to translate (e.g. '1,2,1-,-3,3-5')"
    )
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
    translate_table_text: bool = Field(
        default=True, description="Translate table text (experimental)"
    )
    skip_scanned_detection: bool = Field(
        default=False, description="Skip scanned detection"
    )
    ocr_workaround: bool = Field(
        default=False,
        description="Force translated text to be black and add white background",
    )


class SettingsModel(BaseModel):
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
    gui_settings: GUISettings = Field(default_factory=GUISettings)
    translate_engine_settings: TRANSLATION_ENGINE_SETTING_TYPE | None = Field(
        description="Translation engine settings", discriminator="translate_engine_type"
    )

    def clone(self) -> SettingsModel:
        return self.model_copy(deep=True)

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

        if self.basic.warmup:
            # warmup mode only download and verify assets
            # so no need to validate other settings
            return

        if self.basic.generate_offline_assets and self.basic.restore_offline_assets:
            raise ValueError(
                "generate_offline_assets and restore_offline_assets cannot both be set"
            )

        if self.basic.generate_offline_assets:
            # only generate offline assets
            # so no need to validate other settings
            return

        if not self.translate_engine_settings:
            raise ValueError("Must provide a translation service")

        self.translate_engine_settings.validate_settings()
        if hasattr(self.translate_engine_settings, "transform"):
            from_type = self.translate_engine_settings.translate_engine_type
            self.translate_engine_settings = self.translate_engine_settings.transform()
            to_type = self.translate_engine_settings.translate_engine_type
            log.info(f"Transformed translate_engine_settings: {from_type} -> {to_type}")
            self.translate_engine_settings.validate_settings()

        # Validate files
        for file in self.basic.input_files:
            file_path = Path(file.strip("\"'"))
            if not file_path.exists():
                raise ValueError(f"File does not exist: {file}")
            if not file_path.suffix.lower() == ".pdf":
                raise ValueError(f"File is not a PDF file: {file}")

        # Validate PDF output mode
        if self.pdf.no_dual and self.pdf.no_mono:
            raise ValueError("Cannot disable both dual and mono output modes")

        # Validate regex patterns
        if self.pdf.formular_font_pattern:
            try:
                re.compile(self.pdf.formular_font_pattern)
            except re.error as e:
                raise ValueError(f"Invalid formular_font_pattern: {e}") from e

        if self.pdf.formular_char_pattern:
            try:
                re.compile(self.pdf.formular_char_pattern)
            except re.error as e:
                raise ValueError(f"Invalid formular_char_pattern: {e}") from e

        if self.pdf.enhance_compatibility:
            self.pdf.skip_clean = True
            self.pdf.disable_rich_text_translate = True

        if self.pdf.max_pages_per_part and self.pdf.max_pages_per_part < 0:
            raise ValueError("max_pages_per_part must be greater than 0")

        if self.pdf.watermark_output_mode not in WatermarkOutputMode:
            raise ValueError(
                f"Invalid watermark output mode: {self.pdf.watermark_output_mode}"
            )

        if self.translation.qps < 1:
            raise ValueError("qps must be greater than 0")

        if self.translation.min_text_length < 0:
            raise ValueError("min_text_length must be greater than or equal to 0")

        if self.report_interval < 0.05:
            raise ValueError("report_interval must be greater than or equal to 0.05")

        if self.pdf.split_short_lines and self.pdf.short_line_split_factor < 0.1:
            raise ValueError(
                "short_line_split_factor must be greater than or equal to 0.1"
            )

        if self.pdf.max_pages_per_part < 50:
            raise ValueError("max_pages_per_part must be greater than or equal to 50")

    def parse_pages(self) -> list[tuple[int, int]] | None:
        """Parse pages string into list of page ranges"""
        if not self.pdf.pages:
            return None

        ranges: list[tuple[int, int]] = []
        try:
            for part in self.pdf.pages.split(","):
                part = part.strip()
                if "-" in part:
                    start, end = part.split("-")
                    try:
                        start_as_int = int(start) if start else 1
                        end_as_int = int(end) if end else -1
                        if start_as_int < 1 and start:
                            raise ValueError(f"Invalid start page number: {start}")
                        if end_as_int < -1:
                            raise ValueError(f"Invalid end page number: {end}")
                        if end_as_int != -1 and start_as_int > end_as_int:
                            raise ValueError(
                                f"Start page {start} is greater than end page {end}"
                            )
                        ranges.append((start_as_int, end_as_int))
                    except ValueError as e:
                        if "invalid literal for int()" in str(e):
                            raise ValueError(
                                f"Invalid page number format in range: {part}"
                            ) from e
                        raise
                else:
                    try:
                        page = int(part)
                        if page < 1:
                            raise ValueError(f"Invalid page number: {page}")
                        ranges.append((page, page))
                    except ValueError as e:
                        raise ValueError(f"Invalid page number format: {part}") from e
        except ValueError as e:
            raise ValueError(f"Error parsing pages parameter: {e}") from e

        return ranges
