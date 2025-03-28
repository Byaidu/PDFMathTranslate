from __future__ import annotations

import argparse
import logging
import os
import typing
from inspect import getdoc
from types import NoneType
from typing import Any
from typing import get_args
from typing import get_origin

from pydantic import BaseModel

from pdf2zh.config.model import SettingsModel

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
        cli_settings = self.create_settings_from_args(args).model_dump()

        # Parse environment variables (middle priority)
        env_settings = self.parse_env_vars()

        # Merge all settings by priority
        merged_settings = self.merge_settings(
            [
                cli_settings,
                env_settings,
            ]
        )

        # Create settings model from merged dictionary
        self._settings = SettingsModel(**merged_settings)
        log.debug(f"Initialized settings: {self._settings.model_dump_json()}")

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
            arg_name = arg_name.replace("_", "-").lower()

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
