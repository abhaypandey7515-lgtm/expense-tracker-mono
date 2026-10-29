import random

import pytest

from app.core.money import parse_amount, split_equally
from app.dsa_engines import ActionKind, ActivityStack, DebtSimplificationEngine, StackFrame

E = DebtSimplificationEngine


def _exp(payer, amount, shares):
    return {"payer_id": payer, "amount_minor": amount,
            "shares": [{"user_id": u, "share_minor": s} for u, s in shares.items()]}


def test_parse_amount():
    assert parse_amount("1,250.505") == 125051
    assert parse_amount(450.5) == 45050
    for bad in ("0", "-5", "abc", "nan", "inf", "1e30", ""):
        with pytest.raises(ValueError):
            parse_amount(bad)


def test_split_equally_is_exact():
    sh = split_equally(100, ["a", "b", "c"])
    assert sh == {"a": 34, "b": 33, "c": 33}


def test_graph_nets_opposite_edges():
    exps = [_exp("a", 100, {"a": 50, "b": 50}), _exp("b", 30, {"a": 15, "b": 15})]
    assert E.build_obligation_graph(exps) == {"b": {"a": 35}}


def test_simplify_chain():
    # a owes b 10, b owes c 10  ->  a pays c directly (1 payment instead of 2)
    exps = [_exp("b", 10, {"a": 10}), _exp("c", 10, {"b": 10})]
    res = E.simplify_debts(exps, [], ["a", "b", "c"])
    assert [(t.from_user, t.to_user, t.amount_minor) for t in res.transfers] == [("a", "c", 10)]
    assert res.original_transactions_count == 2 and res.transactions_eliminated == 1


def test_simplify_property_random():
    rnd = random.Random(7)
    for _ in range(300):
        n = rnd.randint(2, 8)
        users = [f"u{i}" for i in range(n)]
        exps, sets = [], []
        for _ in range(rnd.randint(1, 15)):
            amt = rnd.randint(1, 100000)
            parts = rnd.sample(users, rnd.randint(1, n))
            exps.append(_exp(rnd.choice(users), amt, split_equally(amt, parts)))
        for _ in range(rnd.randint(0, 3)):
            f, t = rnd.sample(users, 2)
            sets.append({"from_user_id": f, "to_user_id": t, "amount_minor": rnd.randint(1, 5000)})
        bal = E.compute_net_balances(exps, sets, users)
        assert sum(bal.values()) == 0
        plan = E.simplify_balances(bal)
        assert len(plan) <= n - 1
        after = dict(bal)
        for t in plan:
            assert t.amount_minor > 0
            after[t.from_user] += t.amount_minor
            after[t.to_user] -= t.amount_minor
        assert set(after.values()) <= {0}


def test_stack_is_lifo():
    s = ActivityStack()
    assert s.pop() is None and s.is_empty()
    for i in range(3):
        s.push(StackFrame(id=str(i), group_id="g", kind=ActionKind.EXPENSE, ref_id=str(i)))
    assert s.peek().id == "2" and s.size() == 3
    assert [f.id for f in s.to_list()] == ["2", "1", "0"]
    assert s.pop().id == "2" and s.pop().id == "1" and s.size() == 1
