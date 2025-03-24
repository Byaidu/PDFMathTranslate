import logging

from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

log = logging.getLogger(__name__)


class Settings(BaseSettings):
    input_files: set[str] = set()

    model_config = SettingsConfigDict(env_prefix="PDF2ZH_", cli_parse_args=True)


class ConfigManager:
    pass


print(Settings().model_dump())
