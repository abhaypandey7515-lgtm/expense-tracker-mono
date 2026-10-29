import os
import tempfile
import uuid

# Point the app at a throwaway database BEFORE it is imported.
_tmp = tempfile.mkdtemp(prefix="expense_tracker_test_")
DB_FILE = os.path.join(_tmp, "test.db")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{DB_FILE}"
os.environ["PBKDF2_ITERATIONS"] = "1000"  # fast hashing in tests

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

PW = "correct-horse"


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:  # runs the lifespan, which creates the tables
        yield c


class Person:
    def __init__(self, client, username, display_name, token, user_id):
        self.client, self.username, self.display_name = client, username, display_name
        self.token, self.id = token, user_id

    @property
    def h(self):
        return {"Authorization": f"Bearer {self.token}"}

    def get(self, path, **kw):
        return self.client.get(f"/api/v1{path}", headers=self.h, **kw)

    def post(self, path, json=None, **kw):
        return self.client.post(f"/api/v1{path}", json=json, headers=self.h, **kw)


@pytest.fixture
def make_user(client):
    def _make(name="asha"):
        username = f"{name}_{uuid.uuid4().hex[:8]}"
        r = client.post("/api/v1/auth/register", json={"username": username, "password": PW, "display_name": name.title()})
        assert r.status_code == 201, r.text
        r = client.post("/api/v1/auth/login", json={"username": username, "password": PW})
        assert r.status_code == 200, r.text
        data = r.json()
        return Person(client, username, name.title(), data["token"], data["user"]["id"])
    return _make


@pytest.fixture
def flat(make_user):
    """A group of three people: asha (owner), bhanu, chitra."""
    a, b, c = make_user("asha"), make_user("bhanu"), make_user("chitra")
    g = a.post("/groups", {"name": "Flat 4B"}).json()
    for p in (b, c):
        assert p.post("/groups/join", {"invite_code": g["invite_code"]}).status_code == 200
    return a, b, c, g
