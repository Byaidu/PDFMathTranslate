"""Model and font files for the legacy kernel.

BabelDOC's asset downloader is used when BabelDOC is installed. On Python 3.14,
where BabelDOC cannot be installed, the same files are fetched from the same
Hugging Face repositories with huggingface_hub (which honours HF_ENDPOINT, e.g.
https://hf-mirror.com), into the same cache folder so both paths share them.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

LAYOUT_REPO = "wybxc/DocLayout-YOLO-DocStructBench-onnx"
LAYOUT_FILE = "doclayout_yolo_docstructbench_imgsz1024.onnx"
LAYOUT_SHA3_256 = "60be061226930524958b5465c8c04af3d7c03bcb0beb66454f5da9f792e3cf2a"
FONT_REPO = "awwaawwa/BabelDOC-Assets"  # a dataset repository


def _babeldoc_assets():
    try:
        from babeldoc.assets import assets

        return assets
    except ImportError:
        return None


def _cache_dir(kind: str) -> Path:
    """BabelDOC's cache folder (~/.cache/babeldoc/<kind>)."""
    path = Path(os.path.expanduser("~/.cache/babeldoc")) / kind
    path.mkdir(parents=True, exist_ok=True)
    return path


def _sha3_256(path: Path) -> str:
    digest = hashlib.sha3_256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hf_download(repo_id: str, filename: str, target: Path, **kwargs) -> Path:
    from huggingface_hub import hf_hub_download

    logger.info(f"downloading {filename} from {repo_id}")
    downloaded = Path(hf_hub_download(repo_id, filename, **kwargs))
    tmp = target.with_suffix(target.suffix + ".part")
    tmp.write_bytes(downloaded.read_bytes())
    tmp.replace(target)
    return target


def doclayout_model_path() -> Path:
    """The DocLayout-YOLO ONNX model, downloaded on first use."""
    assets = _babeldoc_assets()
    if assets is not None:
        return Path(assets.get_doclayout_onnx_model_path())
    path = _cache_dir("models") / LAYOUT_FILE
    if path.is_file() and _sha3_256(path) == LAYOUT_SHA3_256:
        return path
    _hf_download(LAYOUT_REPO, LAYOUT_FILE, path)
    if _sha3_256(path) != LAYOUT_SHA3_256:
        path.unlink(missing_ok=True)
        raise RuntimeError(f"{LAYOUT_FILE} failed its checksum; try again")
    return path


def font_path(name: str) -> Path:
    """A font from BabelDOC's font set, downloaded on first use."""
    assets = _babeldoc_assets()
    if assets is not None:
        path, _ = assets.get_font_and_metadata(name)
        return Path(path)
    path = _cache_dir("fonts") / name
    if path.is_file() and path.stat().st_size > 0:
        return path
    # huggingface_hub checks the file against the repository's LFS hash.
    return _hf_download(FONT_REPO, f"fonts/{name}", path, repo_type="dataset")
