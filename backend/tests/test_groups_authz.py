"""Authorization: only members of a group can touch it."""


def test_create_join_and_list(flat, make_user):
    a, b, c, g = flat
    assert len(g["invite_code"]) == 6
    detail = a.get(f"/groups/{g['id']}").json()
    assert {m["display_name"] for m in detail["members"]} == {"Asha", "Bhanu", "Chitra"}
    assert [m["role"] for m in detail["members"]][0] == "owner"
    assert [x["id"] for x in b.get("/groups").json()] == [g["id"]]


def test_join_is_case_insensitive_and_idempotent(flat):
    a, b, c, g = flat
    r = b.post("/groups/join", {"invite_code": g["invite_code"].lower()})
    assert r.status_code == 200
    assert len(a.get(f"/groups/{g['id']}").json()["members"]) == 3


def test_bad_invite_code(make_user):
    assert make_user().post("/groups/join", {"invite_code": "ZZZZZZ"}).status_code == 404


def test_outsider_is_forbidden_everywhere(flat, make_user):
    a, b, c, g = flat
    out = make_user("mallory")
    gid = g["id"]
    a.post(f"/groups/{gid}/expenses", {"amount": "100", "description": "x"})
    for path in ("", "/expenses", "/settlements", "/balances", "/plan", "/categories", "/activity"):
        assert out.get(f"/groups/{gid}{path}").status_code == 403, path
    body = {"amount": "10", "description": "sneaky"}
    assert out.post(f"/groups/{gid}/expenses", body).status_code == 403
    assert out.post(f"/groups/{gid}/undo").status_code == 403
    assert out.post(f"/groups/{gid}/settlements", {"from_user_id": a.id, "to_user_id": b.id, "amount": "1"}).status_code == 403
    # ... and nothing changed.
    assert len(a.get(f"/groups/{gid}/expenses").json()) == 1


def test_unknown_group_looks_like_not_a_member(make_user):
    assert make_user().get("/groups/00000000-0000-0000-0000-000000000000").status_code == 403


def test_unauthenticated_group_access_is_401(flat, client):
    *_, g = flat
    assert client.get(f"/api/v1/groups/{g['id']}/expenses").status_code == 401
    assert client.post(f"/api/v1/groups/{g['id']}/undo").status_code == 401
