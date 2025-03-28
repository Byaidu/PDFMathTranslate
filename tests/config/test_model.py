from pathlib import Path

import pytest
from pdf2zh.config.model import BasicSettings
from pdf2zh.config.model import OpenAISettings
from pdf2zh.config.model import PDFSettings
from pdf2zh.config.model import SettingsModel
from pdf2zh.config.model import TranslationSettings
from pdf2zh.config.model import WatermarkOutputMode
from pydantic import ValidationError


class TestBasicSettings:
    def test_default_values(self):
        """Test default values of BasicSettings"""
        settings = BasicSettings()
        assert settings.input_files == set()
        assert settings.debug is False
        assert settings.warmup is False
        assert settings.rpc_doclayout is None
        assert settings.generate_offline_assets is None
        assert settings.restore_offline_assets is None

    def test_input_files_validation(self):
        """Test input files validation"""
        # Valid input
        settings = BasicSettings(input_files={"test.pdf"})
        assert "test.pdf" in settings.input_files

        # Test with multiple files
        settings = BasicSettings(input_files={"test1.pdf", "test2.pdf"})
        assert len(settings.input_files) == 2
        assert "test1.pdf" in settings.input_files
        assert "test2.pdf" in settings.input_files


class TestTranslationSettings:
    def test_default_values(self):
        """Test default values of TranslationSettings"""
        settings = TranslationSettings()
        assert settings.pages is None
        assert settings.min_text_length == 5
        assert settings.lang_in == "en"
        assert settings.lang_out == "zh"
        assert settings.output is None
        assert settings.qps == 4
        assert settings.ignore_cache is False

    def test_custom_values(self, tmp_path):
        """Test setting custom values"""
        settings = TranslationSettings(
            pages="1-3",
            min_text_length=10,
            lang_in="fr",
            lang_out="es",
            output=str(tmp_path),
            qps=10,
            ignore_cache=True,
        )
        assert settings.pages == "1-3"
        assert settings.min_text_length == 10
        assert settings.lang_in == "fr"
        assert settings.lang_out == "es"
        assert settings.output == str(tmp_path)
        assert settings.qps == 10
        assert settings.ignore_cache is True


class TestPDFSettings:
    def test_default_values(self):
        """Test default values of PDFSettings"""
        settings = PDFSettings()
        assert settings.no_dual is False
        assert settings.no_mono is False
        assert settings.formular_font_pattern is None
        assert settings.formular_char_pattern is None
        assert settings.split_short_lines is False
        assert settings.short_line_split_factor == 0.8
        assert settings.skip_clean is False
        assert settings.dual_translate_first is False
        assert settings.disable_rich_text_translate is False
        assert settings.enhance_compatibility is False
        assert settings.use_alternating_pages_dual is False
        assert settings.watermark_output_mode == WatermarkOutputMode.Watermarked
        assert settings.max_pages_per_part is None
        assert settings.translate_table_text is False

    def test_watermark_mode_validation(self):
        """Test watermark mode validation"""
        # Valid modes
        settings = PDFSettings(watermark_output_mode=WatermarkOutputMode.NoWatermark)
        assert settings.watermark_output_mode == WatermarkOutputMode.NoWatermark

        settings = PDFSettings(watermark_output_mode=WatermarkOutputMode.Both)
        assert settings.watermark_output_mode == WatermarkOutputMode.Both

        # Invalid mode
        with pytest.raises(ValidationError):
            PDFSettings(watermark_output_mode="invalid")


class TestOpenAISettings:
    def test_default_values(self):
        """Test default values of OpenAISettings"""
        settings = OpenAISettings()
        assert settings.openai_model == "gpt-4o-mini"
        assert settings.openai_base_url is None
        assert settings.openai_api_key is None

    def test_alias_fields(self):
        """Test alias field names work correctly"""
        settings = OpenAISettings(
            model="gpt-4",
            **{"base-url": "http://api.example.com", "api-key": "test-key"},
        )
        assert settings.openai_model == "gpt-4"
        assert settings.openai_base_url == "http://api.example.com"
        assert settings.openai_api_key == "test-key"


class TestSettingsModel:
    def test_default_values(self):
        """Test default values of SettingsModel"""
        settings = SettingsModel()
        assert settings.config is None
        assert settings.report_interval == 0.1
        assert settings.openai is False
        assert isinstance(settings.basic, BasicSettings)
        assert isinstance(settings.translation, TranslationSettings)
        assert isinstance(settings.pdf, PDFSettings)
        assert isinstance(settings.openai_detail, OpenAISettings)

    def test_get_output_dir(self, tmp_path: Path):
        """Test get_output_dir method"""
        # Test with specified output directory
        settings = SettingsModel(translation={"output": str(tmp_path / "test_output")})
        output_dir = settings.get_output_dir()
        assert output_dir.exists()
        assert output_dir.is_dir()
        assert str(output_dir) == str(tmp_path / "test_output")

        # Test with default (current) directory
        settings = SettingsModel()
        output_dir = settings.get_output_dir()
        assert output_dir.exists()
        assert output_dir.is_dir()
        assert output_dir == Path.cwd()

    def test_validate_settings(self, tmp_path: Path):
        """Test settings validation"""
        # Test missing translation service
        settings = SettingsModel()
        with pytest.raises(ValueError, match="Must select a translation service"):
            settings.validate_settings()

        # Test missing OpenAI API key
        settings = SettingsModel(openai=True)
        with pytest.raises(ValueError, match="OpenAI API key is required"):
            settings.validate_settings()

        # Test valid OpenAI settings
        settings = SettingsModel(openai=True, openai_detail={"api-key": "test-key"})

        # Create a test PDF file
        test_pdf = tmp_path / "test.pdf"
        test_pdf.write_bytes(b"%PDF-1.4\n")  # Minimal valid PDF content

        settings.basic.input_files = {str(test_pdf)}
        settings.validate_settings()  # Should not raise any error

        # Test invalid input file
        settings = SettingsModel(
            openai=True,
            openai_detail={"api-key": "test-key"},
            basic={"input_files": {"nonexistent.pdf"}},
        )
        with pytest.raises(ValueError, match="File does not exist"):
            settings.validate_settings()

        # Test non-PDF file
        non_pdf = tmp_path / "test.txt"
        non_pdf.touch()
        settings = SettingsModel(
            openai=True,
            openai_detail={"api-key": "test-key"},
            basic={"input_files": {str(non_pdf)}},
        )
        with pytest.raises(ValueError, match="File is not a PDF file"):
            settings.validate_settings()

    def test_parse_pages(self):
        """Test page range parsing"""
        # Test None case
        settings = SettingsModel()
        assert settings.parse_pages() is None

        # Test single page
        settings = SettingsModel(translation={"pages": "1"})
        assert settings.parse_pages() == [(1, 1)]

        # Test page range
        settings = SettingsModel(translation={"pages": "1-3"})
        assert settings.parse_pages() == [(1, 3)]

        # Test multiple ranges
        settings = SettingsModel(translation={"pages": "1,3-5,7"})
        assert settings.parse_pages() == [(1, 1), (3, 5), (7, 7)]

        # Test open-ended ranges
        settings = SettingsModel(translation={"pages": "1-,3,-5"})
        assert settings.parse_pages() == [(1, -1), (3, 3), (1, 5)]

        # Test invalid format
        settings = SettingsModel(translation={"pages": "invalid"})
        with pytest.raises(ValueError):
            settings.parse_pages()
