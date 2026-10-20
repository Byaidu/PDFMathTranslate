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
    """Return an installed kernel: "auto" (legacy, else babeldoc), "babeldoc" or "legacy"."""
    kernel = KernelRegistry.get(name)
    if not kernel.is_available():
        raise RuntimeError(
            f"Kernel '{kernel.name}' is not available. "
            f"Install it with: {INSTALL_HINTS[kernel.name]}"
        )
    return kernel


def warm_up(name: str = "auto") -> None:
    """Load a kernel's models in a background thread, so that a long-running
    server's first translation does not wait for them."""
    import logging
    import threading

    def load():
        try:
            kernel = get_kernel(name)
            if hasattr(kernel, "warm_up"):
                kernel.warm_up()
        except Exception:  # the first translation reports it
            logging.getLogger(__name__).debug("warm-up failed", exc_info=True)

    threading.Thread(target=load, name="pdf2zh-warm-up", daemon=True).start()


def available_kernels() -> list[str]:
    """Names of the installed kernels."""
    return KernelRegistry.available()


__all__ = ["KernelRegistry", "available_kernels", "get_kernel", "warm_up"]
