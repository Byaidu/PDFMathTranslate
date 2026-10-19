import logging

log = logging.getLogger(__name__)

__version__ = "1.9.12"
__author__ = "Byaidu"
__all__ = [
    "TranslateRequest",
    "TranslateResult",
    "available_kernels",
    "get_kernel",
    "translate",
    "translate_stream",
]


def __getattr__(name):
    # Imports stay lazy so `import pdf2zh` and `pdf2zh --version` remain cheap.
    if name in {"translate", "translate_stream"}:
        # Legacy kernel functions, kept for backward compatibility.
        from pdf2zh.high_level import translate, translate_stream

        return {"translate": translate, "translate_stream": translate_stream}[name]
    if name in {"get_kernel", "available_kernels"}:
        from pdf2zh import kernel

        return getattr(kernel, name)
    if name in {"TranslateRequest", "TranslateResult"}:
        from pdf2zh.kernel import protocol

        return getattr(protocol, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
