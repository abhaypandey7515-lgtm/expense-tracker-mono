def _bal(p, gid):
    return p.get(f"/groups/{gid}/balances").json()


def test_equal_split_default_everyone(flat):
    a, b, c, g = flat
    r = a.post(f"/groups/{g['id']}/expenses", {"amount": "100.00", "description": "Milk", "category": "Groceries"})
    assert r.status_code == 201, r.text
    e = r.json()
    assert e["amount_minor"] == 10000 and e["payer_name"] == "Asha"
    shares = sorted(s["share_minor"] for s in e["shares"])
    assert shares == [3333, 3333, 3334] and sum(shares) == 10000  # leftover paise, exact total
    bal = _bal(a, g["id"])
    assert sum(bal["balances"].values()) == 0 and bal["is_balanced"]
    assert bal["balances"][a.id] == 10000 - 3334  # asha is first, so she absorbs the extra paisa


def test_participants_payer_and_custom_shares(flat):
    a, b, c, g = flat
    gid = g["id"]
    r = b.post(f"/groups/{gid}/expenses", {"amount": "90", "description": "Net", "participants": [a.id, b.id]})
    assert sorted(s["share_minor"] for s in r.json()["shares"]) == [4500, 4500]
    r = a.post(f"/groups/{gid}/expenses", {"amount": "60", "description": "Gas", "payer_id": c.id,
                                           "shares": {a.id: "10", c.id: "50"}})
    assert r.status_code == 201 and r.json()["payer_name"] == "Chitra"
    bal = _bal(a, gid)["balances"]
    assert bal[c.id] == 6000 - 5000 and bal[a.id] == -4500 - 1000 and bal[b.id] == 9000 - 4500


def test_validation_errors(flat, make_user):
    a, b, c, g = flat
    gid = g["id"]
    post = lambda body: a.post(f"/groups/{gid}/expenses", body)  # noqa: E731
    for bad in ("0", "-5", "abc", "NaN", "Infinity", "1e30"):
        assert post({"amount": bad, "description": "x"}).status_code == 422, bad
    assert post({"amount": "10", "description": "  "}).status_code == 422
    assert post({"amount": "10", "description": "x", "shares": {a.id: "3"}}).status_code == 400      # != total
    assert post({"amount": "10", "description": "x", "participants": []}).status_code == 400
    outsider = make_user("zed")
    assert post({"amount": "10", "description": "x", "participants": [outsider.id]}).status_code == 400
    assert post({"amount": "10", "description": "x", "payer_id": outsider.id}).status_code == 400
    assert a.get(f"/groups/{gid}/expenses").json() == []


def test_plan_and_settle_to_zero(flat):
    a, b, c, g = flat
    gid = g["id"]
    a.post(f"/groups/{gid}/expenses", {"amount": "300", "description": "Groceries", "category": "Groceries"})
    b.post(f"/groups/{gid}/expenses", {"amount": "90", "description": "Internet", "category": "Internet",
                                       "participants": [a.id, b.id]})
    plan = a.get(f"/groups/{gid}/plan").json()
    assert 1 <= plan["simplified_transactions_count"] <= 2   # at most N-1
    for t in plan["transfers"]:
        r = a.post(f"/groups/{gid}/settlements", {"from_user_id": t["from_user_id"], "to_user_id": t["to_user_id"],
                                                  "amount": f"{t['amount_minor'] / 100:.2f}"})
        assert r.status_code == 201, r.text
    assert set(_bal(a, gid)["balances"].values()) == {0}
    assert a.get(f"/groups/{gid}/plan").json()["transfers"] == []
    assert len(a.get(f"/groups/{gid}/settlements").json()) == len(plan["transfers"])


def test_settlement_validation(flat, make_user):
    a, b, c, g = flat
    gid = g["id"]
    s = lambda f, t, amt: a.post(f"/groups/{gid}/settlements", {"from_user_id": f, "to_user_id": t, "amount": amt})  # noqa: E731
    assert s(a.id, a.id, "5").status_code == 400
    assert s(a.id, make_user("zed").id, "5").status_code == 400
    assert s(a.id, b.id, "0").status_code == 422


def test_category_totals(flat):
    a, b, c, g = flat
    gid = g["id"]
    a.post(f"/groups/{gid}/expenses", {"amount": "100", "description": "a", "category": "Food"})
    a.post(f"/groups/{gid}/expenses", {"amount": "50", "description": "b", "category": "Food"})
    a.post(f"/groups/{gid}/expenses", {"amount": "400", "description": "c", "category": "Rent"})
    assert a.get(f"/groups/{gid}/categories").json() == [
        {"category": "Rent", "total_minor": 40000}, {"category": "Food", "total_minor": 15000}]
    assert _bal(a, gid)["total_spend_minor"] == 55000


def test_undo_is_lifo_across_expenses_and_payments(flat):
    a, b, c, g = flat
    gid = g["id"]
    a.post(f"/groups/{gid}/expenses", {"amount": "10", "description": "first"})
    a.post(f"/groups/{gid}/expenses", {"amount": "20", "description": "second"})
    b.post(f"/groups/{gid}/settlements", {"from_user_id": b.id, "to_user_id": a.id, "amount": "5"})
    assert [f["kind"] for f in a.get(f"/groups/{gid}/activity").json()] == ["settlement", "expense", "expense"]
    r = c.post(f"/groups/{gid}/undo").json()          # any member may undo
    assert r["success"] and r["undone_kind"] == "settlement" and r["remaining_stack_size"] == 2
    assert "second" in a.post(f"/groups/{gid}/undo").json()["message"]
    assert [e["description"] for e in a.get(f"/groups/{gid}/expenses").json()] == ["first"]
    assert a.post(f"/groups/{gid}/undo").json()["success"]
    r = a.post(f"/groups/{gid}/undo").json()
    assert r == {"success": False, "undone_kind": None, "message": "Nothing to undo", "remaining_stack_size": 0}
    assert set(_bal(a, gid)["balances"].values()) == {0}
    assert a.get(f"/groups/{gid}/settlements").json() == []


def test_groups_are_isolated(flat, make_user):
    a, b, c, g = flat
    other = make_user("zed")
    g2 = other.post("/groups", {"name": "Elsewhere"}).json()
    a.post(f"/groups/{g['id']}/expenses", {"amount": "100", "description": "mine"})
    assert other.get(f"/groups/{g2['id']}/expenses").json() == []
    assert other.post(f"/groups/{g2['id']}/undo").json()["success"] is False   # cannot pop another group's stack
    assert len(a.get(f"/groups/{g['id']}/expenses").json()) == 1
