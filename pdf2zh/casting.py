from typing import Any, Optional


def safe_int(o: Any) -> Optional[int]:
    try:
        return int(o)
    except (TypeError, ValueError):
        return None


def safe_float(o: Any) -> Optional[float]:
    try:
        return float(o)
    except (TypeError, ValueError):
        return None
