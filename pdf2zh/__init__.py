import logging
import os
import re

log = logging.getLogger(__name__)


def _normalize_no_proxy() -> None:
    """Rewrite bracketed IPv6 hosts in NO_PROXY ("[::1]" -> "::1").

    Local proxy tools often set NO_PROXY=...,[::1]; httpx 0.28 rejects that
    form with "Invalid port" whenever a client is created, which breaks
    translation services and BabelDOC downloads. httpx accepts "::1".
    """
    for key in ("NO_PROXY", "no_proxy"):
        value = os.environ.get(key)
        if not value or "[" not in value:
            continue
        hosts = []
        for host in value.split(","):
            host = host.strip()
            match = re.fullmatch(r"\[([^\]]+)\](?::\d+)?", host)
            host = match.group(1) if match else host
            if host and host not in hosts:
                hosts.append(host)
        os.environ[key] = ",".join(hosts)


_normalize_no_proxy()

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
