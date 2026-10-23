"""Shared fixtures."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def tiny_data(tmp_path: Path) -> Path:
    """A writable copy of the tiny synthetic dataset (metadata CSVs and tracking/)."""
    target = tmp_path / "data"
    shutil.copytree(FIXTURES / "tiny", target)
    return target
