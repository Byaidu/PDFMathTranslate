"""Kernel package — hot-pluggable translation kernel registry."""

from pdf2zh.kernel.registry import INSTALL_HINTS, KernelRegistry
from pdf2zh.kernel.babeldoc_kernel import BabelDOCKernel
from pdf2zh.kernel.legacy import LegacyKernel
from pdf2zh.kernel.protocol import KernelProtocol

# Always register both kernels; is_available() reports whether the
# optional dependencies of each one are installed.
KernelRegistry.register(BabelDOCKernel())
KernelRegistry.register(LegacyKernel())


def get_kernel(name: str = "auto") -> KernelProtocol:
    """Return an installed kernel: "auto", "babeldoc" or "legacy"."""
    kernel = KernelRegistry.get(name)
    if not kernel.is_available():
        raise RuntimeError(
            f"Kernel '{kernel.name}' is not available. "
            f"Install it with: {INSTALL_HINTS[kernel.name]}"
        )
    return kernel


def available_kernels() -> list[str]:
    """Names of the installed kernels."""
    return KernelRegistry.available()


__all__ = ["KernelRegistry", "available_kernels", "get_kernel"]
