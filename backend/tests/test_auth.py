import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from conftest import DB_FILE, PW


def _name():
    return f"user_{uuid.uuid4().hex[:8]}"


def test_register_login_me_logout(client):
    u = _name()
    assert client.post("/api/v1/auth/register", json={"username": u, "password": PW}).status_code == 201
    r = client.post("/api/v1/auth/login", json={"username": u, "password": PW})
    assert r.status_code == 200
    tok = r.json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert client.get("/api/v1/auth/me", headers=h).json()["username"] == u
    assert client.post("/api/v1/auth/logout", headers=h).status_code == 204
    # The token stops working immediately: the session row is gone.
    assert client.get("/api/v1/auth/me", headers=h).status_code == 401


def test_password_is_not_stored_in_clear(client):
    u = _name()
    client.post("/api/v1/auth/register", json={"username": u, "password": "plaintext-secret"})
    con = sqlite3.connect(DB_FILE)
    h, s = con.execute("SELECT pw_hash, salt FROM users WHERE username=?", (u,)).fetchone()
    con.close()
    assert b"plaintext-secret" not in h and len(s) == 16 and len(h) == 32


def test_username_unique_case_insensitive(client):
    u = _name()
    assert client.post("/api/v1/auth/register", json={"username": u, "password": PW}).status_code == 201
    assert client.post("/api/v1/auth/register", json={"username": u.upper(), "password": PW}).status_code == 409


def test_register_validation(client):
    assert client.post("/api/v1/auth/register", json={"username": "ab", "password": PW}).status_code == 422
    assert client.post("/api/v1/auth/register", json={"username": "has space", "password": PW}).status_code == 422
    assert client.post("/api/v1/auth/register", json={"username": _name(), "password": "short"}).status_code == 422


def test_wrong_password_and_unknown_user_look_identical(client):
    u = _name()
    client.post("/api/v1/auth/register", json={"username": u, "password": PW})
    bad_pw = client.post("/api/v1/auth/login", json={"username": u, "password": "nope-nope"})
    no_user = client.post("/api/v1/auth/login", json={"username": _name(), "password": "nope-nope"})
    assert bad_pw.status_code == no_user.status_code == 401
    assert bad_pw.json() == no_user.json()


def test_missing_or_garbage_token_is_401(client):
    assert client.get("/api/v1/groups").status_code == 401
    assert client.get("/api/v1/groups", headers={"Authorization": "Bearer not-a-token"}).status_code == 401


def test_expired_session_is_rejected(client, make_user):
    p = make_user("dev")
    assert p.get("/auth/me").status_code == 200
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S.%f")
    con = sqlite3.connect(DB_FILE)
    con.execute("UPDATE sessions SET expires_at=? WHERE token=?", (past, p.token))
    con.commit()
    con.close()
    assert p.get("/auth/me").status_code == 401
