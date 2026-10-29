"""Money helpers. Every amount is stored as an integer number of paise/cents."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Dict, List, Union

MAX_AMOUNT_MINOR = 100_000_000_000  # 1 billion major units


def parse_amount(value: Union[str, int, float, Decimal]) -> int:
    """'450.50' -> 45050. Raises ValueError for junk, NaN/inf, <= 0 or absurdly large values."""
    try:
        d = Decimal(str(value).replace(",", "").strip())
    except InvalidOperation as e:
        raise ValueError(f"Invalid amount: {value!r}") from e
    if not d.is_finite():
        raise ValueError(f"Invalid amount: {value!r}")
    if d <= 0:
        raise ValueError("Amount must be greater than zero")
    if d > Decimal(MAX_AMOUNT_MINOR) / 100:  # check before scaling: huge values overflow Decimal's context
        raise ValueError("Amount is too large")
    minor = int((d * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    if minor <= 0:  # e.g. 0.001 rounds to nothing
        raise ValueError("Amount must be greater than zero")
    return minor


def split_equally(total_minor: int, user_ids: List[str]) -> Dict[str, int]:
    """Split a total across users; leftover paise go to the first users so shares sum exactly."""
    if not user_ids:
        raise ValueError("Need at least one participant")
    base, extra = divmod(total_minor, len(user_ids))
    return {uid: base + (1 if i < extra else 0) for i, uid in enumerate(user_ids)}
