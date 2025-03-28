from __future__ import annotations

import argparse
import logging
import os
import typing
from inspect import getdoc
from pathlib import Path
from types import NoneType
from typing import Any
from typing import get_args
from typing import get_origin

import tomlkit
from pydantic import BaseModel

from pdf2zh.config.model import SettingsModel
from pdf2zh.const import DEFAULT_CONFIG_DIR
from pdf2zh.const import DEFAULT_CONFIG_FILE
from pdf2zh.const import VERSION_DEFAULT_CONFIG_FILE

log = logging.getLogger(__name__)


class MagicDefault:
    pass


def build_args_parser(
    parser: argparse.ArgumentParser | None = None,
    settings_model: BaseModel | None = None,
    field_name2type: dict[str, Any] | None = None,
    recursion_depth: int = 0,
) -> tuple[argparse.ArgumentParser, dict[str, Any]]:
    if parser is None:
        parser = argparse.ArgumentParser()

    if field_name2type is None:
        field_name2type = {}

    if settings_model is not None:
        parser = parser.add_argument_group(
            title=settings_model.__name__,
            description=getdoc(settings_model),
        )
    else:
        settings_model = SettingsModel

    for field_name, field_detail in settings_model.model_fields.items():
        if field_name in field_name2type:
            log.critical(f"duplicate field name: {field_name}")
            raise ValueError(f"duplicate field name: {field_name}")
        field_name2type[field_name] = field_detail.annotation
        if field_detail.default_factory is not None:
            if recursion_depth > 0:
                raise ValueError("not supported nested settings models")
            build_args_parser(
                parser,
                field_detail.default_factory,
                field_name2type,
                recursion_depth + 1,
            )
        else:
            type_hint = typing.get_type_hints(settings_model)[field_name]
            original_type = typing.get_origin(type_hint)
            args = typing.get_args(type_hint)
            log.debug(
                f"field_name: {field_name}, type_hint: {type_hint}, original_type: {original_type}, args: {args}"
            )
            if original_type is None:
                args = [type_hint]
            args_name = field_name.replace("_", "-").lower()
            for arg in args:
                if arg is bool:
                    parser.add_argument(
                        f"--{args_name}",
                        action="store_true"
                        if field_detail.default is False
                        else "store_false",
                        default=MagicDefault,
                        help=field_detail.description,
                    )
                elif arg == NoneType:
                    continue
                else:
                    parser.add_argument(
                        f"--{args_name}",
                        type=arg,
                        default=MagicDefault,
                        help=field_detail.description,
                    )
    return parser, field_name2type


class ConfigManager:
    """Singleton configuration manager"""

    _instance: ConfigManager | None = None
    _settings: SettingsModel | None = None
    _field_name2type: dict[str, Any] | None = None

    def __new__(cls) -> ConfigManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            _, field_name2type = build_args_parser(None, SettingsModel)
            cls._field_name2type = field_name2type
        return cls._instance

    def _ensure_config_dir(self) -> None:
        """Ensure the configuration directory exists"""
        DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    def _read_toml_file(self, file_path: Path) -> dict:
        """Read and parse a TOML file

        Args:
            file_path: Path to the TOML file

        Returns:
            Parsed TOML content as dictionary
        """
        try:
            with file_path.open(encoding="utf-8") as f:
                content = tomlkit.load(f)
                # Convert "null" strings back to None
                return self._process_toml_content(dict(content))
        except FileNotFoundError:
            log.debug(f"Config file not found: {file_path}")
            return {}
        except Exception as e:
            log.warning(f"Error reading config file {file_path}: {e}")
            return {}

    def _process_toml_content(self, content: dict) -> dict:
        """Process TOML content recursively, converting special values

        Args:
            content: Dictionary from TOML file

        Returns:
            Processed dictionary
        """
        result = {}
        for key, value in content.items():
            if isinstance(value, dict):
                result[key] = self._process_toml_content(value)
            elif isinstance(value, str) and value == "null":
                result[key] = None
            else:
                result[key] = value
        return result

    def _write_toml_file(self, file_path: Path, content: dict) -> None:
        """Write content to a TOML file

        Args:
            file_path: Path to write the TOML file
            content: Content to write as dictionary
        """
        try:
            # Convert None to "null" string
            toml_content = tomlkit.document()
            for key, value in content.items():
                if isinstance(value, dict):
                    section = tomlkit.table()
                    for k, v in value.items():
                        section.add(k, "null" if v is None else v)
                    toml_content.add(key, section)
                else:
                    toml_content.add(key, "null" if value is None else value)

            with file_path.open("w", encoding="utf-8") as f:
                tomlkit.dump(toml_content, f)
        except Exception as e:
            log.warning(f"Error writing config file {file_path}: {e}")

    def _is_file_content_identical(self, file_path: Path, content: dict) -> bool:
        """Check if file content is identical to the given content

        Args:
            file_path: Path to the file to check
            content: Content to compare with

        Returns:
            True if content is identical, False otherwise
        """
        try:
            existing_content = self._read_toml_file(file_path)
            return existing_content == content
        except Exception:
            return False

    def _get_default_config(self) -> dict:
        """Get default configuration from model

        Returns:
            Default configuration as dictionary
        """
        default_model = SettingsModel()
        config_dict = default_model.model_dump(mode="json")

        # Convert sets to lists for TOML serialization
        if "basic" in config_dict and "input_files" in config_dict["basic"]:
            config_dict["basic"]["input_files"] = list(
                config_dict["basic"]["input_files"]
            )

        return config_dict

    def _update_version_default_config(self) -> None:
        """Update version default configuration file if needed"""
        self._ensure_config_dir()
        default_config = self._get_default_config()

        # Always write if file doesn't exist
        if (
            not VERSION_DEFAULT_CONFIG_FILE.exists()
            or not self._is_file_content_identical(
                VERSION_DEFAULT_CONFIG_FILE, default_config
            )
        ):
            self._write_toml_file(VERSION_DEFAULT_CONFIG_FILE, default_config)
            log.debug("Updated version default configuration file")

    def parse_cli_args(self) -> None:
        """Parse command line arguments"""
        parser, _ = build_args_parser()
        args = parser.parse_args()
        log.debug(f"CLI args: {args}")
        self._settings = self.create_settings_from_args(args)
        log.debug(f"Settings from CLI: {self._settings.model_dump_json()}")

    def parse_env_vars(self) -> dict:
        """Parse environment variables into a settings dictionary

        Returns:
            Dictionary with settings derived from environment variables
        """
        if self._field_name2type is None:
            raise RuntimeError("ConfigManager not properly initialized")

        env_settings = {}

        for field_name, type_hint in self._field_name2type.items():
            # Convert field name to environment variable format (uppercase)
            env_name = f"PDF2ZH_{field_name.upper()}"

            if env_name in os.environ:
                # Get the value from environment
                env_value = os.environ[env_name]

                # Get type information for proper conversion
                origin_type = get_origin(type_hint)
                type_args = get_args(type_hint)

                # Convert the value to the appropriate type
                try:
                    converted_value = self._convert_env_value(
                        env_value, type_hint, origin_type, type_args
                    )
                    # Add to settings dict
                    env_settings[field_name] = converted_value
                except (ValueError, TypeError) as e:
                    log.warning(
                        f"Could not convert environment variable {env_name}: {e}"
                    )
                else:
                    log.warning(f"Field {field_name} not found in type hints")

        log.debug(f"Environment settings: {env_settings}")
        return env_settings

    def _convert_env_value(
        self, value: str, type_hint: Any, origin_type: Any, type_args: tuple
    ) -> Any:
        """
        Convert environment variable string value to the appropriate type

        Args:
            value: String value from environment variable
            type_hint: The type hint for the field
            origin_type: The origin type (e.g., list, dict)
            type_args: Type arguments for generic types

        Returns:
            Converted value matching the expected type
        """
        # Handle Union types (including Optional)
        if origin_type is typing.Union:
            # Try each type in the Union until one works
            for arg in type_args:
                if arg is NoneType and value.lower() in ("none", ""):
                    return None
                try:
                    return self._convert_env_value(
                        value, arg, get_origin(arg), get_args(arg)
                    )
                except (ValueError, TypeError):
                    continue
            # If no conversion worked, raise error
            raise ValueError(
                f"Could not convert '{value}' to any of the types: {type_args}"
            )

        # Handle basic types
        if type_hint is bool:
            return value.lower() in ("true", "1", "yes", "y", "on")
        elif type_hint is int:
            return int(value)
        elif type_hint is float:
            return float(value)
        elif type_hint is str:
            return value

        # For other types, try direct conversion
        return type_hint(value)

    def _deep_merge(self, target: dict, source: dict) -> dict:
        """
        Deep merge two dictionaries

        Args:
            target: Target dictionary to merge into
            source: Source dictionary to merge from

        Returns:
            Merged dictionary
        """
        for key, value in source.items():
            if (
                key in target
                and isinstance(target[key], dict)
                and isinstance(value, dict)
            ):
                self._deep_merge(target[key], value)
            elif (
                key in target
                and isinstance(target[key], list)
                and isinstance(value, list)
            ):
                target[key].extend(value)
            else:
                target[key] = value
        return target

    def merge_settings(self, config_dicts: list[dict]) -> dict:
        """
        Merge multiple configuration dictionaries based on priority

        Args:
            config_dicts: List of config dictionaries, ordered by priority (highest first)

        Returns:
            Merged configuration dictionary
        """
        result = {}
        # Process from lowest to highest priority
        for config in reversed(config_dicts):
            # Deep merge config into result
            self._deep_merge(result, config)

        return result

    def initialize_config(self) -> None:
        """Initialize configuration from all sources"""
        # Parse CLI arguments (highest priority)
        parser, _ = build_args_parser()
        args = parser.parse_args()
        cli_args = {k: v for k, v in vars(args).items() if v is not MagicDefault}

        # Parse environment variables (middle priority)
        env_vars = self.parse_env_vars()

        # Read default configuration file (lower priority)
        default_config_file = self._read_toml_file(DEFAULT_CONFIG_FILE)

        # Merge all settings by priority
        merged_args = self.merge_settings(
            [
                cli_args,
                env_vars,
            ]
        )
        if "config_file" in merged_args:
            user_config = self._read_toml_file(Path(merged_args["config_file"]))
            del merged_args["config_file"]
            merged_args = self.merge_settings(
                [merged_args, user_config, default_config_file]
            )
        # Create settings model from merged dictionary
        self._settings = self._build_model_from_args(SettingsModel, merged_args)
        log.debug(f"Initialized settings: {self._settings.model_dump_json()}")

        # Update version default configuration if needed
        self._update_version_default_config()

    def create_settings_from_args(self, args: argparse.Namespace) -> SettingsModel:
        """
        Create SettingsModel instance from parsed command line arguments

        Args:
            args: Parsed command line arguments

        Returns:
            SettingsModel instance with values from command line args
        """
        args_dict = vars(args)

        # Build the model directly without pre-building a field map
        settings = self._build_model_from_args(SettingsModel, args_dict)
        assert isinstance(settings, SettingsModel)
        return settings

    def _build_model_from_args(
        self, model_class: type[BaseModel], args_dict: dict
    ) -> BaseModel:
        """
        Recursively build model instances from arguments dictionary

        Args:
            model_class: Pydantic model class to instantiate
            args_dict: Dictionary of arguments

        Returns:
            Instance of the specified model class
        """
        model_kwargs = {}

        # Process all fields in the model
        for field_name, field_detail in model_class.model_fields.items():
            # Get the corresponding CLI argument name
            arg_name = field_detail.alias or field_name
            arg_name = (
                arg_name.replace("_", "-").lower()
                if arg_name not in args_dict
                else arg_name
            )

            # If the argument was provided, add it to the kwargs
            if arg_name in args_dict and args_dict[arg_name] is not None:
                args = args_dict[arg_name]
                if isinstance(args, MagicDefault) or args == MagicDefault:
                    # If the argument is a MagicDefault, skip it
                    continue
                model_kwargs[field_name] = args_dict[arg_name]

            # Handle nested models
            if field_detail.default_factory is not None:
                nested_model_class = field_detail.default_factory
                model_kwargs[field_name] = self._build_model_from_args(
                    nested_model_class, args_dict
                )

        # Create and return the model instance
        return model_class(**model_kwargs)

    @property
    def settings(self) -> SettingsModel:
        """Get current settings"""
        if self._settings is None:
            raise RuntimeError("Settings not initialized")
        return self._settings


# disable not necessary log for normal usage
log.setLevel(logging.INFO)

if __name__ == "__main__":
    # only for debug
    log.setLevel(logging.DEBUG)
    logging.basicConfig(level=logging.DEBUG)

    config_manager = ConfigManager()
    # Use the new initialization method that combines CLI and env vars
    config_manager.initialize_config()
