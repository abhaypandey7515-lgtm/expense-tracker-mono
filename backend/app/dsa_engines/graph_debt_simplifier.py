"""
Debt simplification engine.

Data structures and algorithms:
  * Hash map (dict)      - net balance per member, O(1) update/lookup.
  * Directed graph       - debtor -> creditor edges weighted by the amount owed, netted pairwise.
  * Heaps (heapq)        - greedy min-cash-flow: repeatedly match the largest debtor with the
                           largest creditor. Settles everyone in at most N-1 payments, O(N log N).

All amounts are integer paise, so balances always sum to exactly zero.
"""

import heapq
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class Transfer:
    from_user: str
    to_user: str
    amount_minor: int


@dataclass
class SimplificationResult:
    net_balances: Dict[str, int]
    transfers: List[Transfer]
    original_transactions_count: int      # edges in the netted obligation graph
    simplified_transactions_count: int
    transactions_eliminated: int
    efficiency_gain_percent: float


class DebtSimplificationEngine:
    @staticmethod
    def compute_net_balances(
        expenses: Iterable[Dict[str, Any]],
        settlements: Iterable[Dict[str, Any]] = (),
        member_ids: Optional[Iterable[str]] = None,
    ) -> Dict[str, int]:
        """
        expenses:    {"payer_id", "amount_minor", "shares": [{"user_id", "share_minor"}]}
        settlements: {"from_user_id", "to_user_id", "amount_minor"}
        Positive balance = is owed money, negative = owes money.
        """
        bal: Dict[str, int] = defaultdict(int)
        for m in member_ids or ():
            bal[m] = 0
        for e in expenses:
            bal[e["payer_id"]] += e["amount_minor"]
            for s in e["shares"]:
                bal[s["user_id"]] -= s["share_minor"]
        for s in settlements:
            bal[s["from_user_id"]] += s["amount_minor"]
            bal[s["to_user_id"]] -= s["amount_minor"]
        return dict(bal)

    @staticmethod
    def build_obligation_graph(
        expenses: Iterable[Dict[str, Any]],
        settlements: Iterable[Dict[str, Any]] = (),
    ) -> Dict[str, Dict[str, int]]:
        """graph[debtor][creditor] = amount owed, with opposite edges between a pair netted out."""
        raw: Dict[tuple, int] = defaultdict(int)
        for e in expenses:
            for s in e["shares"]:
                if s["user_id"] != e["payer_id"]:
                    raw[(s["user_id"], e["payer_id"])] += s["share_minor"]
        for s in settlements:
            raw[(s["from_user_id"], s["to_user_id"])] -= s["amount_minor"]
        graph: Dict[str, Dict[str, int]] = defaultdict(dict)
        for (a, b), w in raw.items():
            net = w - raw.get((b, a), 0)
            if net > 0:
                graph[a][b] = net
        return dict(graph)

    @staticmethod
    def simplify_balances(balances: Dict[str, int]) -> List[Transfer]:
        # Max-heaps via negated amounts; the user id breaks ties so output is deterministic.
        creditors = [(-b, u) for u, b in balances.items() if b > 0]
        debtors = [(b, u) for u, b in balances.items() if b < 0]  # most negative first
        heapq.heapify(creditors)
        heapq.heapify(debtors)
        out: List[Transfer] = []
        while creditors and debtors:
            c_neg, c = heapq.heappop(creditors)
            d_neg, d = heapq.heappop(debtors)
            c_amt, d_amt = -c_neg, -d_neg
            pay = min(c_amt, d_amt)
            out.append(Transfer(d, c, pay))
            if c_amt > pay:
                heapq.heappush(creditors, (-(c_amt - pay), c))
            if d_amt > pay:
                heapq.heappush(debtors, (-(d_amt - pay), d))
        return out

    @classmethod
    def simplify_debts(
        cls,
        expenses: List[Dict[str, Any]],
        settlements: List[Dict[str, Any]],
        member_ids: Optional[Iterable[str]] = None,
    ) -> SimplificationResult:
        balances = cls.compute_net_balances(expenses, settlements, member_ids)
        graph = cls.build_obligation_graph(expenses, settlements)
        original = sum(len(v) for v in graph.values())
        transfers = cls.simplify_balances(balances)
        saved = max(0, original - len(transfers))
        return SimplificationResult(
            net_balances=balances,
            transfers=transfers,
            original_transactions_count=original,
            simplified_transactions_count=len(transfers),
            transactions_eliminated=saved,
            efficiency_gain_percent=round(saved / original * 100.0, 1) if original else 0.0,
        )
