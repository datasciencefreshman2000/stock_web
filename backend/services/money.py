"""Decimal arithmetic at money boundaries; public JSON remains numeric."""
from decimal import Decimal, ROUND_HALF_UP


def decimal(value=0) -> Decimal:
    return Decimal(str(value if value is not None else 0))


def money_sum(values) -> float:
    return float(sum((decimal(value) for value in values), Decimal(0)))


def rounded(value, places=8) -> float:
    return float(decimal(value).quantize(Decimal(10) ** -places, rounding=ROUND_HALF_UP))
