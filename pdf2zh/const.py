__version__ = "2.0.0.rc0"

from pathlib import Path

# Constants for configuration paths
DEFAULT_CONFIG_DIR = Path("~/.config/pdf2zh").expanduser()
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "default.toml"
VERSION_DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "version.default.toml"
