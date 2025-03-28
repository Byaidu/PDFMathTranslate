import os
from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture
def temp_pdf_file(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary PDF file for testing"""
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(b"%PDF-1.4\n")  # Minimal valid PDF content
    yield pdf_file
    if pdf_file.exists():
        pdf_file.unlink()


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove all PDF2ZH_ environment variables"""
    for key in os.environ:
        if key.startswith("PDF2ZH_"):
            monkeypatch.delenv(key)
