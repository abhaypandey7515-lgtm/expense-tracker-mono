"""TUI tests run against the real backend (in-process), so login, sessions and group
authorization are exercised end to end."""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

_tmp = tempfile.mkdtemp(prefix="expense_tracker_tui_test_")
DB_FILE = os.path.join(_tmp, "test.db")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{DB_FILE}"
os.environ["PBKDF2_ITERATIONS"] = "1000"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from expense_tracker_tui.client import ApiClient  # noqa: E402


@pytest.fixture(scope="session")
def http():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client(http):
    return ApiClient(http=http)


@pytest.fixture
def expire_session():
    def _expire(token: str):
        con = sqlite3.connect(DB_FILE)
        con.execute("UPDATE sessions SET expires_at='2000-01-01 00:00:00.000000' WHERE token=?", (token,))
        con.commit()
        con.close()
    return _expire
