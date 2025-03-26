from __future__ import annotations

import argparse
import logging
import typing
from inspect import getdoc
from types import NoneType

from pydantic import BaseModel

from pdf2zh.config.model import SettingsModel

log = logging.getLogger(__name__)


class MagicDefault:
    pass


def build_args_parser(
    parser: argparse.ArgumentParser | None = None,
    settings_model: BaseModel | None = None,
    field_name_set: set[str] | None = None,
) -> argparse.ArgumentParser:
    if parser is None:
        parser = argparse.ArgumentParser()

    if field_name_set is None:
        field_name_set = set()

    if settings_model is not None:
        parser = parser.add_argument_group(
            title=settings_model.__name__,
            description=getdoc(settings_model),
        )
    else:
        settings_model = SettingsModel
    for field_name, field_detail in settings_model.model_fields.items():
        if field_name in field_name_set:
            log.critical(f"duplicate field name: {field_name}")
            raise ValueError(f"duplicate field name: {field_name}")
        field_name_set.add(field_name)
        if field_detail.default_factory is not None:
            if settings_model != SettingsModel:
                raise ValueError("not supported nested settings models")
            build_args_parser(parser, field_detail.default_factory, field_name_set)
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
                        default=MagicDefault(),
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
    return parser


class ConfigManager:
    """Singleton configuration manager"""

    _instance: ConfigManager | None = None
    _settings: SettingsModel | None = None

    def __new__(cls) -> ConfigManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def parse_cli_args(self) -> None:
        """Parse command line arguments"""
        parser = build_args_parser()
        args = parser.parse_args()
        print(args)
        self._settings = self.create_settings_from_args(args)
        print(self._settings.model_dump_json())

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
    config_manager.parse_cli_args()
