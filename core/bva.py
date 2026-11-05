"""Boundary Value Analysis."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from .models import Case, FieldSpec
from .values import SpecError, materialize, midpoint, parse_range, shift, unit_label

MODES = ("2-value", "3-value", "robust")
MODE_HELP = {
    "2-value": "min-1, min, max, max+1 (4 values per range)",
    "3-value": "min-1, min, min+1, max-1, max, max+1 (6 values per range)",
    "robust": "3-value + nominal value + extreme values (0, -1, INT_MAX, leap day ...)",
}


def _first_leap_day(lo: date, hi: date) -> date | None:
    for y in range(lo.year, min(hi.year, 9999) + 1):
        try:
            d = date(y, 2, 29)
        except ValueError:
            continue
        if lo <= d <= hi:
            return d
    return None


def _month_end(d: date) -> date:
    first_next = date(d.year + 1, 1, 1) if d.month == 12 else date(d.year, d.month + 1, 1)
    return shift(first_next, -1, 1, "date")


def range_boundaries(spec: FieldSpec, mode: str = "3-value") -> tuple[list[Case], list[str]]:
    """BVA cases for int / decimal / string-length / date fields."""
    if mode not in MODES:
        raise SpecError(f"Unknown boundary mode '{mode}'.")
    lo, hi, step = parse_range(spec)
    t, nm = spec.type, spec.name
    unit = unit_label(step, t)
    cases: list[Case] = []
    notes: list[str] = []

    def add(v: Any, partition: str, why: str, technique: str = "BVA") -> None:
        if v is None:
            notes.append(f"{nm}: '{partition}' skipped (outside the supported date range).")
            return
        if t == "string" and v < 0:
            notes.append(f"{nm}: '{partition}' skipped - a length below 0 is impossible.")
            return
        cases.append(Case(materialize(v, t), technique, partition, lo <= v <= hi, why))

    add(shift(lo, -1, step, t), "Just below min", f"min - {unit}")
    add(lo, "Min", "lower boundary")
    if mode != "2-value":
        add(shift(lo, 1, step, t), "Just above min", f"min + {unit}")
        add(shift(hi, -1, step, t), "Just below max", f"max - {unit}")
    add(hi, "Max", "upper boundary")
    add(shift(hi, 1, step, t), "Just above max", f"max + {unit}")

    if mode == "robust":
        add(midpoint(lo, hi, t), "Nominal (mid-range)", "typical value in the middle of the range",
            "BVA-robust")
        extremes: list[tuple[Any, str]] = []
        if t == "int":
            extremes = [(0, "Extreme: zero"), (-1, "Extreme: negative one"),
                        (2147483647, "Extreme: INT_MAX"), (-2147483648, "Extreme: INT_MIN")]
        elif t == "decimal":
            extremes = [(Decimal("0"), "Extreme: zero"), (Decimal("-1"), "Extreme: negative one"),
                        (Decimal("999999999.99"), "Extreme: very large")]
        elif t == "string":
            extremes = [(1, "Extreme: single character"), (255, "Extreme: 255 chars"),
                        (1000, "Extreme: 1000 chars")]
        elif t == "date":
            extremes = [(date(1900, 1, 1), "Extreme: very old date"),
                        (date(1970, 1, 1), "Extreme: Unix epoch"),
                        (date(9999, 12, 31), "Extreme: max date")]
            leap = _first_leap_day(lo, hi)
            if leap:
                extremes.append((leap, "Leap day (Feb 29)"))
            me = _month_end(lo)
            if lo <= me <= hi:
                extremes.append((me, "Month end"))
        for v, label in extremes:
            add(v, label, "extreme / special value", "BVA-robust")
    return cases, notes
