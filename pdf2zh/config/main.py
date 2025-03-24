from __future__ import annotations

import argparse
import logging
import typing
from inspect import getdoc
from types import NoneType

from pydantic import BaseModel

from pdf2zh.config.model import SettingsModel

log = logging.getLogger(__name__)


def build_args_parser(
    parser: argparse.ArgumentParser | None = None,
    settings_model: BaseModel | None = None,
) -> argparse.ArgumentParser:
    if parser is None:
        parser = argparse.ArgumentParser()

    if settings_model is not None:
        parser = parser.add_argument_group(
            title=settings_model.__name__,
            description=getdoc(settings_model),
        )
    else:
        settings_model = SettingsModel
    for field_name, field_detail in settings_model.model_fields.items():
        if field_detail.default_factory is not None:
            if settings_model != SettingsModel:
                raise ValueError("not supported nested settings models")
            build_args_parser(parser, field_detail.default_factory)
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
                        action="store_true",
                        default=field_detail.default,
                        help=field_detail.description,
                    )
                elif arg == NoneType:
                    continue
                else:
                    parser.add_argument(
                        f"--{args_name}",
                        type=arg,
                        default=field_detail.default,
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
        pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    config_manager = ConfigManager()
    config_manager.parse_cli_args()
