from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app
from app.store import store


@pytest.fixture(autouse=True)
def reset_store() -> None:
    store.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)

