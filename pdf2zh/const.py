__version__ = "2.0.0.rc0"

from pathlib import Path

# Constants for configuration paths
DEFAULT_CONFIG_DIR = Path("~/.config/pdf2zh").expanduser()
DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "default.toml"
VERSION_DEFAULT_CONFIG_DIR = DEFAULT_CONFIG_DIR / "default"
VERSION_DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
VERSION_DEFAULT_CONFIG_FILE = VERSION_DEFAULT_CONFIG_DIR / f"{__version__}.toml"
