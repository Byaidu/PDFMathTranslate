"""Regression tests for legacy high_level.translate file handling."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from pdf2zh import high_level


def test_translate_keeps_input_files_in_temp_dir():
    # Inputs that happen to live in the temp dir (e.g. browser downloads in
    # /tmp) belong to the user and must survive translation.
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "paper.pdf"
        source.write_bytes(b"%PDF-1.7 placeholder")
        with patch.object(
            high_level, "translate_stream", return_value=(b"mono", b"dual")
        ):
            result = high_level.translate(files=[str(source)], output=tmp)

        assert source.exists()
        assert Path(result[0][0]).read_bytes() == b"mono"
        assert Path(result[0][1]).read_bytes() == b"dual"
