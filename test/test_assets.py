"""Tests for the legacy kernel's model and font downloads without BabelDOC."""

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pdf2zh import assets  # noqa: E402

MODEL = b"onnx model bytes"


class TestAssetsWithoutBabelDOC(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.hub = self.tmp / "hub"
        self.hub.mkdir()
        self.patches = [
            patch.object(assets, "_babeldoc_assets", return_value=None),
            patch.object(assets, "_cache_dir", side_effect=self.cache_dir),
            patch.object(
                assets, "LAYOUT_SHA3_256", hashlib.sha3_256(MODEL).hexdigest()
            ),
        ]
        for p in self.patches:
            p.start()
        self.downloads = []

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def cache_dir(self, kind):
        path = self.tmp / "cache" / kind
        path.mkdir(parents=True, exist_ok=True)
        return path

    def fake_hub(self, data):
        def download(repo_id, filename, **kwargs):
            self.downloads.append((repo_id, filename, kwargs))
            path = self.hub / filename.replace("/", "_")
            path.write_bytes(data)
            return str(path)

        return patch("huggingface_hub.hf_hub_download", side_effect=download)

    def test_model_is_downloaded_once(self):
        with self.fake_hub(MODEL):
            first = assets.doclayout_model_path()
            second = assets.doclayout_model_path()
        self.assertEqual(first, second)
        self.assertEqual(first.read_bytes(), MODEL)
        self.assertEqual(len(self.downloads), 1)
        self.assertEqual(
            self.downloads[0][:2], (assets.LAYOUT_REPO, assets.LAYOUT_FILE)
        )

    def test_corrupt_model_is_rejected(self):
        with self.fake_hub(b"truncated"), self.assertRaises(RuntimeError):
            assets.doclayout_model_path()
        self.assertFalse((self.tmp / "cache" / "models" / assets.LAYOUT_FILE).exists())

    def test_font_comes_from_the_dataset_repository(self):
        with self.fake_hub(b"font"):
            path = assets.font_path("GoNotoKurrent-Regular.ttf")
            assets.font_path("GoNotoKurrent-Regular.ttf")
        self.assertEqual(path.read_bytes(), b"font")
        self.assertEqual(len(self.downloads), 1)
        repo, filename, kwargs = self.downloads[0]
        self.assertEqual(
            (repo, filename), (assets.FONT_REPO, "fonts/GoNotoKurrent-Regular.ttf")
        )
        self.assertEqual(kwargs, {"repo_type": "dataset"})


if __name__ == "__main__":
    unittest.main()
