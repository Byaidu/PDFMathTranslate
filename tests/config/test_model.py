from pathlib import Path

import pytest
from pdf2zh.config.cli_env_model import CLIEnvSettingsModel
from pdf2zh.config.model import BasicSettings
from pdf2zh.config.model import PDFSettings
from pdf2zh.config.model import TranslationSettings
from pdf2zh.config.model import WatermarkOutputMode
from pdf2zh.config.translate_engine_model import OpenAISettings
from pydantic import ValidationError


class TestBasicSettings:
    def test_default_values(self):
        """Test default values of BasicSettings"""
        settings = BasicSettings()
        assert settings.input_files == set()
        assert settings.debug is False
        assert settings.warmup is False
        # rpc_doclayout has been moved to TranslationSettings
        # assert settings.rpc_doclayout is None
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

    def test_warmup_mode(self):
        """Test warmup mode validation"""
        settings = CLIEnvSettingsModel(basic={"warmup": True})
        # Warmup mode should bypass other validations
        settings.validate_settings()  # Should not raise any error

    def test_offline_assets_mutual_exclusion(self):
        """Test mutual exclusion of offline assets options"""
        settings = CLIEnvSettingsModel(
            basic={
                "generate_offline_assets": "path1",
                "restore_offline_assets": "path2",
            }
        )
        with pytest.raises(
            ValueError,
            match="generate_offline_assets and restore_offline_assets cannot both be set",
        ):
            settings.validate_settings()

        # Test generate_offline_assets alone should work
        settings = CLIEnvSettingsModel(basic={"generate_offline_assets": "path1"})
        settings.validate_settings()  # Should not raise any error


class TestTranslationSettings:
    def test_default_values(self):
        """Test default values of TranslationSettings"""
        settings = TranslationSettings()
        assert settings.min_text_length == 5
        assert settings.lang_in == "en"
        assert settings.lang_out == "zh"
        assert settings.output is None
        assert settings.qps == 4
        assert settings.ignore_cache is False

    def test_custom_values(self, tmp_path):
        """Test setting custom values"""
        settings = TranslationSettings(
            min_text_length=10,
            lang_in="fr",
            lang_out="es",
            output=str(tmp_path),
            qps=10,
            ignore_cache=True,
        )
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
        assert settings.translate_table_text is True

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

    def test_output_modes_mutual_exclusion(self):
        """Test mutual exclusion of PDF output modes"""
        settings = CLIEnvSettingsModel(
            openai=True,
            openai_detail={"openai_api_key": "test-key"},
            pdf={"no_dual": True, "no_mono": True},
        )
        with pytest.raises(
            ValueError, match="Cannot disable both dual and mono output modes"
        ):
            settings.validate_settings()

    def test_formula_patterns(self):
        """Test formula pattern validation"""
        # Test invalid font pattern
        settings = CLIEnvSettingsModel(
            openai=True,
            openai_detail={"openai_api_key": "test-key"},
            pdf={"formular_font_pattern": "["},
        )
        with pytest.raises(ValueError, match="Invalid formular_font_pattern"):
            settings.validate_settings()

        # Test invalid char pattern
        settings = CLIEnvSettingsModel(
            openai=True,
            openai_detail={"openai_api_key": "test-key"},
            pdf={"formular_char_pattern": "["},
        )
        with pytest.raises(ValueError, match="Invalid formular_char_pattern"):
            settings.validate_settings()

        # Test valid patterns
        settings = CLIEnvSettingsModel(
            openai=True,
            openai_detail={"openai_api_key": "test-key"},
            pdf={"formular_font_pattern": r"\w+", "formular_char_pattern": r"\d+"},
        )
        settings.validate_settings()  # Should not raise any error

    def test_page_split_settings(self):
        """Test page split related settings"""
        # Test invalid max_pages_per_part
        settings = CLIEnvSettingsModel(
            openai=True,
            openai_detail={"openai_api_key": "test-key"},
            pdf={"max_pages_per_part": -1},
        )
        with pytest.raises(
            ValueError, match="max_pages_per_part must be greater than 0"
        ):
            settings.validate_settings()

        # Test invalid short_line_split_factor
        settings = CLIEnvSettingsModel(
            openai=True,
            openai_detail={"openai_api_key": "test-key"},
            pdf={"split_short_lines": True, "short_line_split_factor": 0.05},
        )
        with pytest.raises(
            ValueError,
            match="short_line_split_factor must be greater than or equal to 0.1",
        ):
            settings.validate_settings()


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
            openai_model="gpt-4",
            **{
                "openai_base_url": "http://api.example.com",
                "openai_api_key": "test-key",
            },
        )
        assert settings.openai_model == "gpt-4"
        assert settings.openai_base_url == "http://api.example.com"
        assert settings.openai_api_key == "test-key"

    def test_base_url_handling(self):
        """Test base URL handling"""
        # Test URL with /chat/completions/ suffix
        settings = CLIEnvSettingsModel(
            openai=True,
            openai_detail={
                "openai_api_key": "test-key",
                "openai_base_url": "http://api.example.com/chat/completions/",
            },
        ).to_settings_model()
        # Store original URL
        original_url = settings.translate_engine_settings.openai_base_url
        settings.validate_settings()
        # URL should be modified after validation
        assert original_url == "http://api.example.com/chat/completions/"
        assert (
            settings.translate_engine_settings.openai_base_url
            == "http://api.example.com"
        )

        # Test URL contains /chat/completions/
        settings = CLIEnvSettingsModel(
            openai=True,
            openai_detail={
                "openai_api_key": "test-key",
                "openai_base_url": "http://api.example.com/chat/completions/anything",
            },
        ).to_settings_model()
        # Store original URL
        original_url = settings.translate_engine_settings.openai_base_url
        settings.validate_settings()
        # URL should be modified after validation
        assert original_url == "http://api.example.com/chat/completions/anything"
        assert (
            settings.translate_engine_settings.openai_base_url
            == "http://api.example.com/chat/completions/anything"
        )

        # Test URL without /chat/completions/ suffix
        settings = CLIEnvSettingsModel(
            openai=True,
            openai_detail={
                "openai_api_key": "test-key",
                "openai_base_url": "http://api.example.com",
            },
        )
        original_url = settings.openai_detail.openai_base_url
        settings.validate_settings()
        # URL should remain unchanged
        assert original_url == "http://api.example.com"
        assert settings.openai_detail.openai_base_url == "http://api.example.com"


class TestCLIEnvSettingsModel:
    def test_default_values(self):
        """Test default values of CLIEnvSettingsModel"""
        settings = CLIEnvSettingsModel()
        assert settings.config_file is None
        assert settings.report_interval == 0.1
        assert settings.openai is False
        assert isinstance(settings.basic, BasicSettings)
        assert isinstance(settings.translation, TranslationSettings)
        assert isinstance(settings.pdf, PDFSettings)
        assert isinstance(settings.openai_detail, OpenAISettings)

    def test_get_output_dir(self, tmp_path: Path):
        """Test get_output_dir method"""
        # Test with specified output directory
        settings = CLIEnvSettingsModel(
            translation={"output": str(tmp_path / "test_output")}
        ).to_settings_model()
        output_dir = settings.get_output_dir()
        assert output_dir.exists()
        assert output_dir.is_dir()
        assert str(output_dir) == str(tmp_path / "test_output")

        # Test with default (current) directory
        settings = CLIEnvSettingsModel().to_settings_model()
        output_dir = settings.get_output_dir()
        assert output_dir.exists()
        assert output_dir.is_dir()
        assert output_dir == Path.cwd()

    def test_validate_settings(self, tmp_path: Path):
        """Test settings validation"""
        # Test missing translation service
        settings = CLIEnvSettingsModel()
        settings.validate_settings()

        # Test missing OpenAI API key
        settings = CLIEnvSettingsModel(openai=True)
        with pytest.raises(ValueError, match="OpenAI API key is required"):
            settings.validate_settings()

        # Test valid OpenAI settings
        settings = CLIEnvSettingsModel(
            openai=True, openai_detail={"openai_api_key": "test-key"}
        )

        # Create a test PDF file
        test_pdf = tmp_path / "test.pdf"
        test_pdf.write_bytes(b"%PDF-1.4\n")  # Minimal valid PDF content

        settings.basic.input_files = {str(test_pdf)}
        settings.validate_settings()  # Should not raise any error

        # Test invalid input file
        settings = CLIEnvSettingsModel(
            openai=True,
            openai_detail={"openai_api_key": "test-key"},
            basic={"input_files": {"nonexistent.pdf"}},
        )
        with pytest.raises(ValueError, match="File does not exist"):
            settings.validate_settings()

        # Test non-PDF file
        non_pdf = tmp_path / "test.txt"
        non_pdf.touch()
        settings = CLIEnvSettingsModel(
            openai=True,
            openai_detail={"openai_api_key": "test-key"},
            basic={"input_files": {str(non_pdf)}},
        )
        with pytest.raises(ValueError, match="File is not a PDF file"):
            settings.validate_settings()

    def test_parse_pages(self):
        """Test page range parsing"""
        # Test None case
        settings = CLIEnvSettingsModel().to_settings_model()
        assert settings.parse_pages() is None

        # Test single page
        settings = CLIEnvSettingsModel(pdf={"pages": "1"}).to_settings_model()
        assert settings.parse_pages() == [(1, 1)]

        # Test page range
        settings = CLIEnvSettingsModel(pdf={"pages": "1-3"}).to_settings_model()
        assert settings.parse_pages() == [(1, 3)]

        # Test multiple ranges
        settings = CLIEnvSettingsModel(pdf={"pages": "1,3-5,7"}).to_settings_model()
        assert settings.parse_pages() == [(1, 1), (3, 5), (7, 7)]

        # Test open-ended ranges
        settings = CLIEnvSettingsModel(pdf={"pages": "1-,3,-5"}).to_settings_model()
        assert settings.parse_pages() == [(1, -1), (3, 3), (1, 5)]

        # Test invalid format
        settings = CLIEnvSettingsModel(pdf={"pages": "invalid"}).to_settings_model()
        with pytest.raises(ValueError):
            settings.parse_pages()

    def test_enhance_compatibility_effects(self):
        """Test enhance_compatibility setting effects"""
        settings = CLIEnvSettingsModel(
            openai=True,
            openai_detail={"openai_api_key": "test-key"},
            pdf={"enhance_compatibility": True},
        ).to_settings_model()
        settings.validate_settings()
        assert settings.pdf.skip_clean is True
        assert settings.pdf.disable_rich_text_translate is True

    def test_boundary_values(self):
        """Test boundary value validations"""
        # Test QPS validation
        settings = CLIEnvSettingsModel(
            openai=True,
            openai_detail={"openai_api_key": "test-key"},
            translation={"qps": 0},
        )
        with pytest.raises(ValueError, match="qps must be greater than 0"):
            settings.validate_settings()

        # Test min_text_length validation
        settings = CLIEnvSettingsModel(
            openai=True,
            openai_detail={"openai_api_key": "test-key"},
            translation={"min_text_length": -1},
        )
        with pytest.raises(
            ValueError, match="min_text_length must be greater than or equal to 0"
        ):
            settings.validate_settings()

        # Test report_interval validation
        settings = CLIEnvSettingsModel(
            openai=True,
            openai_detail={"openai_api_key": "test-key"},
            report_interval=0.04,
        )
        with pytest.raises(
            ValueError, match="report_interval must be greater than or equal to 0.05"
        ):
            settings.validate_settings()
