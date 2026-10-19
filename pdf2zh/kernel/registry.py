"""Thread-safe kernel registry for hot-pluggable kernel switching."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pdf2zh.kernel.protocol import KernelProtocol

# Old names from the `--mode` flag, kept so existing commands keep working.
ALIASES = {"fast": "legacy", "precise": "babeldoc"}
# `auto` picks the first available kernel in this order.
AUTO_ORDER = ("babeldoc", "legacy")

INSTALL_HINTS = {
    "babeldoc": "pip install pdf2zh",
    "legacy": "pip install 'pdf2zh[legacy]'",
}


class KernelRegistry:
    _lock = threading.RLock()
    _active: KernelProtocol | None = None
    _kernels: dict[str, KernelProtocol] = {}

    @classmethod
    def register(cls, kernel: KernelProtocol) -> None:
        with cls._lock:
            cls._kernels[kernel.name] = kernel

    @classmethod
    def resolve(cls, name: str | None = None) -> str:
        """Map an alias or "auto" to a registered kernel name."""
        with cls._lock:
            if not name or name == "auto":
                for candidate in AUTO_ORDER:
                    kernel = cls._kernels.get(candidate)
                    if kernel and kernel.is_available():
                        return candidate
                raise RuntimeError(
                    "No translation kernel is installed. Run: pip install pdf2zh"
                )
            return ALIASES.get(name, name)

    @classmethod
    def get(cls, name: str | None = None) -> KernelProtocol:
        with cls._lock:
            if name:
                return cls._kernels[cls.resolve(name)]
            if cls._active:
                return cls._active
            return cls._kernels[cls.resolve("auto")]

    @classmethod
    def switch(cls, name: str) -> None:
        with cls._lock:
            resolved = cls.resolve(name)
            kernel = cls._kernels[resolved]
            if not kernel.is_available():
                hint = INSTALL_HINTS.get(resolved)
                raise RuntimeError(
                    f"Kernel '{resolved}' is not available."
                    + (f" Install it with: {hint}" if hint else "")
                )
            cls._active = kernel

    @classmethod
    def active_name(cls) -> str:
        with cls._lock:
            return cls._active.name if cls._active else cls.resolve("auto")

    @classmethod
    def available(cls) -> list[str]:
        with cls._lock:
            return [n for n, k in cls._kernels.items() if k.is_available()]

    @classmethod
    def _reset(cls) -> None:
        """Reset registry state. For testing only."""
        with cls._lock:
            cls._active = None
            cls._kernels.clear()
