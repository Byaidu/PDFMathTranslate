from __future__ import annotations

from argparse import Namespace
from unittest.mock import patch

import pytest
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
        assert "config" in field_name2type
        assert "report_interval" in field_name2type
        assert "openai" in field_name2type


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
