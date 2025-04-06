from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from unittest.mock import mock_open
from unittest.mock import patch

import pytest
import tomlkit
from pdf2zh.config.main import ConfigManager
from pdf2zh.config.main import MagicDefault
from pdf2zh.config.main import build_args_parser
from pydantic import BaseModel
from pydantic import Field


class NestedModel(BaseModel):
    field1: str
    field2: int


class DuplicateModel(BaseModel):
    field1: str
    nested: NestedModel = Field(default_factory=NestedModel)


class TestBuildArgsParser:
    def test_basic_parser_creation(self):
        """Test basic parser creation"""
        parser, field_name2type = build_args_parser()
        assert parser is not None
        assert field_name2type is not None
        assert isinstance(field_name2type, dict)

    def test_duplicate_field_detection(self):
        """Test duplicate field detection"""
        with pytest.raises(ValueError, match="duplicate field name"):
            build_args_parser(settings_model=DuplicateModel)

    def test_field_types(self):
        """Test different field types are handled correctly"""
        parser, field_name2type = build_args_parser()

        # Check some known fields
        assert "config_file" in field_name2type
        assert "basic" in field_name2type
        assert "translation" in field_name2type


class TestConfigManager:
    def test_singleton(self):
        """Test ConfigManager singleton pattern"""
        cm1 = ConfigManager()
        cm2 = ConfigManager()
        assert cm1 is cm2

    def test_parse_env_vars(self, monkeypatch: pytest.MonkeyPatch):
        """Test environment variable parsing"""
        # Set up test environment variables
        test_env = {
            "PDF2ZH_DEBUG": "true",
            "PDF2ZH_REPORT_INTERVAL": "0.5",
            "PDF2ZH_QPS": "10",
            "PDF2ZH_INPUT_FILES": '["test1.pdf", "test2.pdf"]',
            "PDF2ZH_INVALID_KEY": "value",  # Should be ignored
        }
        for key, value in test_env.items():
            monkeypatch.setenv(key, value)

        cm = ConfigManager()
        env_settings = cm.parse_env_vars()

        assert env_settings["debug"] is True
        assert env_settings["report_interval"] == 0.5
        assert env_settings["qps"] == 10
        assert "invalid_key" not in env_settings

    def test_convert_env_value(self):
        """Test environment variable value conversion"""
        cm = ConfigManager()

        # Test boolean conversion
        assert cm._convert_env_value("true", bool, None, ()) is True
        assert cm._convert_env_value("1", bool, None, ()) is True
        assert cm._convert_env_value("false", bool, None, ()) is False
        assert cm._convert_env_value("0", bool, None, ()) is False

        # Test numeric conversion
        assert cm._convert_env_value("42", int, None, ()) == 42
        assert cm._convert_env_value("3.14", float, None, ()) == 3.14

        # Test string passthrough
        assert cm._convert_env_value("test", str, None, ()) == "test"

        # Test invalid conversions
        with pytest.raises(ValueError):
            cm._convert_env_value("not_a_number", int, None, ())

    def test_deep_merge(self):
        """Test dictionary deep merge"""
        cm = ConfigManager()

        # Test basic merge
        target = {"a": 1, "b": 2}
        source = {"b": 3, "c": 4}
        result = cm._deep_merge(target, source)
        assert result == {"a": 1, "b": 3, "c": 4}

        # Test nested merge
        target = {"a": {"x": 1, "y": 2}, "b": 3}
        source = {"a": {"y": 3, "z": 4}, "c": 5}
        result = cm._deep_merge(target, source)
        assert result == {"a": {"x": 1, "y": 3, "z": 4}, "b": 3, "c": 5}

        # Test list merge
        target = {"a": [1, 2], "b": 3}
        source = {"a": [3, 4], "c": 5}
        result = cm._deep_merge(target, source)
        assert result == {"a": [1, 2, 3, 4], "b": 3, "c": 5}

    def test_merge_settings(self):
        """Test settings merge with priority"""
        cm = ConfigManager()

        cli_settings = {"debug": True, "qps": 10}
        env_settings = {"debug": False, "report_interval": 0.5}
        default_settings = {"debug": False, "qps": 5, "report_interval": 0.1}

        result = cm.merge_settings([cli_settings, env_settings, default_settings])

        # CLI settings should take precedence
        assert result["debug"] is True
        assert result["qps"] == 10
        # Env settings should take precedence over defaults
        assert result["report_interval"] == 0.5

    def test_initialize_config(self, monkeypatch: pytest.MonkeyPatch):
        """Test complete configuration initialization"""
        # Set up environment variables
        monkeypatch.setenv("PDF2ZH_REPORT_INTERVAL", "0.5")
        monkeypatch.setenv("PDF2ZH_QPS", "10")

        # Create a ConfigManager instance
        cm = ConfigManager()

        # Mock command line arguments
        args = Namespace(
            debug=True,
            report_interval=MagicDefault,  # Should use env var
            qps=15,  # Should override env var
        )

        # Initialize configuration
        with patch("argparse.ArgumentParser.parse_args", return_value=args):
            cm.initialize_config()

        # Verify settings
        assert cm.settings.basic.debug is True
        assert cm.settings.translation.qps == 15  # CLI value should override env var
        assert cm.settings.report_interval == 0.5  # Should use env var
        assert cm.settings is not None

    @pytest.fixture
    def sample_toml_content(self) -> str:
        """Sample TOML configuration content"""
        return """
        debug = true
        report_interval = 0.5
        qps = 10
        """

    @pytest.fixture
    def temp_config_dir(self, tmp_path: Path) -> Path:
        """Create a temporary config directory"""
        config_dir = tmp_path / ".config" / "pdf2zh"
        config_dir.mkdir(parents=True)
        return config_dir

    def test_read_toml_file(self, sample_toml_content: str):
        """Test reading TOML configuration file"""
        cm = ConfigManager()

        # Test successful read
        with patch("pathlib.Path.open", mock_open(read_data=sample_toml_content)):
            config = cm._read_toml_file(Path("test.toml"))
            assert config["debug"] is True
            assert config["report_interval"] == 0.5
            assert config["qps"] == 10

        # Test file not found
        with patch("pathlib.Path.open", side_effect=FileNotFoundError):
            config = cm._read_toml_file(Path("nonexistent.toml"))
            assert config == {}

        # Test invalid TOML
        with patch("pathlib.Path.open", mock_open(read_data="invalid = toml [")):
            config = cm._read_toml_file(Path("invalid.toml"))
            assert config == {}

    def test_write_toml_file(self, temp_config_dir: Path):
        """Test writing TOML configuration file"""
        cm = ConfigManager()
        test_file = temp_config_dir / "test.toml"
        test_content = {"debug": True, "report_interval": 0.5}

        # Test successful write
        cm._write_toml_file(test_file, test_content)
        assert test_file.exists()

        # Verify content
        with test_file.open() as f:
            loaded_content = tomlkit.load(f)
            assert dict(loaded_content) == test_content

    def test_is_file_content_identical(self, sample_toml_content: str):
        """Test comparing file content with given content"""
        cm = ConfigManager()
        test_content = {"debug": True, "report_interval": 0.5, "qps": 10}

        # Test identical content
        with patch("pathlib.Path.open", mock_open(read_data=sample_toml_content)):
            assert cm._is_file_content_identical(Path("test.toml"), test_content)

        # Test different content
        different_content = {"debug": False, "report_interval": 1.0}
        assert not cm._is_file_content_identical(Path("test.toml"), different_content)

    def test_update_version_default_config(self, temp_config_dir: Path):
        """Test updating version default configuration file"""
        cm = ConfigManager()
        version_file = temp_config_dir / "version.default.toml"

        with (
            patch.object(ConfigManager, "_ensure_config_dir"),
            patch("pdf2zh.config.main.VERSION_DEFAULT_CONFIG_FILE", version_file),
        ):
            # First update should create the file
            cm._update_version_default_config()
            assert version_file.exists()

            # Test that calling update again doesn't raise errors
            # We can't reliably check for identical mtime due to platform differences
            # and the speed of test execution, so just verify it executes without errors
            cm._update_version_default_config()
            assert version_file.exists()  # File should still exist

    def test_config_file_priority(
        self, monkeypatch: pytest.MonkeyPatch, temp_config_dir: Path
    ):
        """Test configuration file priority order"""
        cm = ConfigManager()

        # Create test files
        user_config = temp_config_dir / "user.toml"
        default_config = temp_config_dir / "default.toml"

        # Set up test configurations
        user_config_content = {"debug": True, "qps": 20}
        default_config_content = {"debug": False, "qps": 10, "report_interval": 0.5}

        with patch("pdf2zh.const.DEFAULT_CONFIG_FILE", default_config):
            # Write test configurations
            cm._write_toml_file(user_config, user_config_content)
            cm._write_toml_file(default_config, default_config_content)

            # Set up environment and CLI args
            monkeypatch.setenv("PDF2ZH_REPORT_INTERVAL", "1.0")
            args = Namespace(
                config_file=str(user_config),
                debug=MagicDefault,
                qps=MagicDefault,
                report_interval=MagicDefault,
            )

            # Initialize configuration
            with patch("argparse.ArgumentParser.parse_args", return_value=args):
                cm.initialize_config()

            # Verify priority: CLI > Env > User Config > Default Config
            assert cm.settings.basic.debug is True  # from user config
            assert cm.settings.translation.qps == 20  # from user config
            assert cm.settings.report_interval == 1.0  # from env var

    def test_ensure_config_dir(self, temp_config_dir: Path):
        """Test configuration directory creation"""
        cm = ConfigManager()
        test_dir = temp_config_dir / "subdir"

        with patch("pdf2zh.config.main.DEFAULT_CONFIG_DIR", test_dir):
            # Directory should not exist initially
            assert not test_dir.exists()

            # Create directory
            cm._ensure_config_dir()
            assert test_dir.exists()
            assert test_dir.is_dir()

            # Should not raise error when directory already exists
            cm._ensure_config_dir()
            assert test_dir.exists()

    def test_process_toml_content(self):
        """Test processing of TOML content with various data types and structures"""
        cm = ConfigManager()

        # Test basic types
        content = {
            "string": "value",
            "number": 42,
            "float": 3.14,
            "bool": True,
            "null_str": "null",
        }
        processed = cm._process_toml_content(content)
        assert processed["string"] == "value"
        assert processed["number"] == 42
        assert processed["float"] == 3.14
        assert processed["bool"] is True
        assert processed["null_str"] is None

        # Test nested structures
        nested_content = {
            "level1": {
                "level2": {"value": "null", "list": [1, 2, 3], "nested_null": "null"}
            }
        }
        processed = cm._process_toml_content(nested_content)
        assert processed["level1_level2_value"] is None
        assert processed["level1_level2_list"] == [1, 2, 3]
        assert processed["level1_level2_nested_null"] is None

    def test_complex_env_vars(self, monkeypatch: pytest.MonkeyPatch):
        """Test parsing of complex environment variables"""
        cm = ConfigManager()

        # Test basic types first
        monkeypatch.setenv("PDF2ZH_DEBUG", "true")
        monkeypatch.setenv("PDF2ZH_QPS", "20")
        env_settings = cm.parse_env_vars()
        assert "debug" in env_settings
        assert env_settings["debug"] is True
        assert env_settings["qps"] == 20

        # Test optional types
        monkeypatch.setenv("PDF2ZH_REPORT_INTERVAL", "0.5")
        env_settings = cm.parse_env_vars()
        assert env_settings["report_interval"] == 0.5

    def test_get_default_config(self):
        """Test default configuration generation"""
        cm = ConfigManager()
        default_config = cm._get_default_config()

        # Verify basic structure
        assert isinstance(default_config, dict)
        # Check for flattened structure with basic_ prefix instead of basic section
        assert any(key.startswith("basic_") for key in default_config)
        assert any(key.startswith("translation_") for key in default_config)

        # Verify input_files is converted to list
        input_files_key = [
            k for k in default_config.keys() if k.endswith("input_files")
        ]
        if input_files_key:
            assert isinstance(default_config[input_files_key[0]], list)

        # Verify essential configuration fields
        assert "basic_debug" in default_config
        assert "translation_qps" in default_config
        assert isinstance(default_config["basic_debug"], bool)
        assert isinstance(default_config["translation_qps"], int | float)

    def test_settings_not_initialized(self):
        """Test accessing settings before initialization"""
        cm = ConfigManager()
        cm._settings = None  # Force settings to be None
        with pytest.raises(RuntimeError, match="Settings not initialized"):
            _ = cm.settings

    def test_initialize_config_with_invalid_file(self, monkeypatch: pytest.MonkeyPatch):
        """Test initialization with invalid config file"""
        cm = ConfigManager()

        # Create args with non-existent config file
        args = Namespace(
            config_file="nonexistent.toml",
            debug=MagicDefault,
            report_interval=MagicDefault,
        )

        # Mock command line arguments
        with patch("argparse.ArgumentParser.parse_args", return_value=args):
            # Should not raise exception, should use default values
            cm.initialize_config()
            assert cm.settings is not None

    def test_initialize_config_with_invalid_toml(self, temp_config_dir: Path):
        """Test initialization with invalid TOML content"""
        cm = ConfigManager()
        invalid_config = temp_config_dir / "invalid.toml"

        # Create invalid TOML file
        invalid_config.write_text("invalid = toml [ content")

        args = Namespace(
            config_file=str(invalid_config),
            debug=MagicDefault,
            report_interval=MagicDefault,
        )

        # Mock command line arguments
        with patch("argparse.ArgumentParser.parse_args", return_value=args):
            # Should not raise exception, should use default values
            cm.initialize_config()
            assert cm.settings is not None

    def test_nested_config_priority(self, monkeypatch: pytest.MonkeyPatch):
        """Test priority handling with nested configurations"""
        cm = ConfigManager()

        # Set up nested configurations at different levels
        cli_args = {"translation": {"model": "gpt-4", "temperature": 0.8}}

        env_vars = {
            "translation": {"model": "gpt-3.5", "temperature": 0.7, "max_tokens": 1000}
        }

        default_config = {
            "translation": {
                "model": "gpt-3",
                "temperature": 0.5,
                "max_tokens": 500,
                "timeout": 30,
            }
        }

        # Test merging with priority
        result = cm.merge_settings([cli_args, env_vars, default_config])

        # CLI values should take precedence
        assert result["translation"]["model"] == "gpt-4"
        assert result["translation"]["temperature"] == 0.8

        # Env vars should take precedence over defaults
        assert result["translation"]["max_tokens"] == 1000

        # Default values should be preserved if not overridden
        assert result["translation"]["timeout"] == 30

    def test_parse_cli_args(self):
        """Test command line argument parsing"""
        cm = ConfigManager()

        # Test with basic argument types
        test_args = [
            "--debug",
            "--qps",
            "20",
            "--report-interval",
            "0.5",
            "file1.pdf",  # Single file for now
        ]

        with patch("sys.argv", ["script.py"] + test_args):
            cm.parse_cli_args()

            assert cm.settings.basic.debug is True
            assert cm.settings.translation.qps == 20
            assert cm.settings.report_interval == 0.5
            # input_files should be empty set by default
            assert isinstance(cm.settings.basic.input_files, set)
            assert len(cm.settings.basic.input_files) == 1

        # Test with input files
        test_args_with_files = ["--debug", "file1.pdf", "file2.pdf"]

        with patch("sys.argv", ["script.py"] + test_args_with_files):
            cm.parse_cli_args()
            assert isinstance(cm.settings.basic.input_files, set)
            assert "file1.pdf" in cm.settings.basic.input_files
            assert "file2.pdf" in cm.settings.basic.input_files

    def test_end_to_end_config(
        self, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Test end-to-end configuration with all sources"""
        cm = ConfigManager()

        # Create test config file
        config_file = temp_config_dir / "test_config.toml"
        config_content = """
        [basic]
        debug = false
        
        [translation]
        model = "gpt-3"
        qps = 5
        """
        config_file.write_text(config_content)

        # Set environment variables
        monkeypatch.setenv("PDF2ZH_QPS", "10")
        monkeypatch.setenv("PDF2ZH_REPORT_INTERVAL", "1.0")

        # Create CLI arguments
        args = Namespace(
            config_file=str(config_file),
            debug=True,  # Should override config file
            qps=MagicDefault,  # Should use env var
            report_interval=MagicDefault,  # Should use env var
            input_files={"test.pdf"},  # Add a test file
        )

        # Initialize with all sources
        with patch("argparse.ArgumentParser.parse_args", return_value=args):
            cm.initialize_config()

            # Verify priority order
            assert cm.settings.basic.debug is True  # From CLI
            assert cm.settings.translation.qps == 10  # From env var
            assert cm.settings.report_interval == 1.0  # From env var
            assert "test.pdf" in cm.settings.basic.input_files  # From CLI args

    def test_file_system_operations(self, temp_config_dir: Path):
        """Test actual file system operations"""
        cm = ConfigManager()

        # Test directory creation
        test_dir = temp_config_dir / "new_config_dir"
        with patch("pdf2zh.config.main.DEFAULT_CONFIG_DIR", test_dir):
            cm._ensure_config_dir()
            assert test_dir.exists()
            assert test_dir.is_dir()

        # Test file writing and reading
        test_file = test_dir / "test.toml"
        test_content = {"basic": {"debug": True}, "translation": {"qps": 15}}

        # Write file
        cm._write_toml_file(test_file, test_content)
        assert test_file.exists()

        # Read and verify content
        read_content = cm._read_toml_file(test_file)
        assert read_content["basic_debug"] is True
        assert read_content["translation_qps"] == 15
