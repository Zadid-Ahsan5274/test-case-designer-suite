"""Parsing, arithmetic and display helpers for field values."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from .models import FIELD_TYPES, RANGE_TYPES, FieldSpec


class SpecError(ValueError):
    """Raised for invalid user input. Messages are meant to be shown to the user."""


def is_blank(x: Any) -> bool:
    return x is None or (isinstance(x, str) and x.strip() == "") or (isinstance(x, float) and x != x)


def to_int(x: Any, label: str) -> int:
    if is_blank(x):
        raise SpecError(f"{label} is required.")
    try:
        d = Decimal(str(x).strip())
    except InvalidOperation:
        raise SpecError(f"{label} must be a whole number (got {x!r}).") from None
    if not d.is_finite() or d != d.to_integral_value():
        raise SpecError(f"{label} must be a whole number (got {x!r}).")
    return int(d)


def to_decimal(x: Any, label: str) -> Decimal:
    if is_blank(x):
        raise SpecError(f"{label} is required.")
    try:
        d = Decimal(str(x).strip())
    except InvalidOperation:
        raise SpecError(f"{label} must be a number (got {x!r}).") from None
    if not d.is_finite():
        raise SpecError(f"{label} must be a finite number (got {x!r}).")
    return d


def to_date(x: Any, label: str) -> date:
    if isinstance(x, date):
        return x
    if is_blank(x):
        raise SpecError(f"{label} is required.")
    try:
        return date.fromisoformat(str(x).strip())
    except ValueError:
        raise SpecError(f"{label} must be a date as YYYY-MM-DD (got {x!r}).") from None


def parse_range(spec: FieldSpec) -> tuple[Any, Any, Any]:
    """Return (lo, hi, step) in the field's internal domain.

    int / string -> ints (string = length), decimal -> Decimal, date -> date (step in days).
    """
    t, nm = spec.type, spec.name or "Field"
    if t == "int":
        lo, hi = to_int(spec.min, f"{nm}: Min"), to_int(spec.max, f"{nm}: Max")
        step = 1 if is_blank(spec.step) else to_int(spec.step, f"{nm}: Step")
    elif t == "string":
        lo, hi = to_int(spec.min, f"{nm}: Min length"), to_int(spec.max, f"{nm}: Max length")
        if lo < 0:
            raise SpecError(f"{nm}: Min length cannot be negative.")
        step = 1
    elif t == "decimal":
        lo, hi = to_decimal(spec.min, f"{nm}: Min"), to_decimal(spec.max, f"{nm}: Max")
        step = Decimal("0.01") if is_blank(spec.step) else to_decimal(spec.step, f"{nm}: Step")
    elif t == "date":
        lo, hi = to_date(spec.min, f"{nm}: Min"), to_date(spec.max, f"{nm}: Max")
        step = 1 if is_blank(spec.step) else to_int(spec.step, f"{nm}: Step (days)")
    else:
        raise SpecError(f"{nm}: type '{t}' has no numeric range.")
    if step <= 0:
        raise SpecError(f"{nm}: Step must be greater than 0.")
    if lo > hi:
        raise SpecError(f"{nm}: Min ({display(lo)}) is greater than Max ({display(hi)}).")
    return lo, hi, step


def shift(v: Any, k: int, step: Any, t: str) -> Any:
    """v + k*step in the right domain. Returns None if a date overflows."""
    try:
        if t in ("int", "string"):
            return v + k * step
        if t == "decimal":
            return v + step * k
        if t == "date":
            return v + timedelta(days=step * k)
    except OverflowError:
        return None
    raise SpecError(f"Unsupported type {t}")


def midpoint(lo: Any, hi: Any, t: str) -> Any:
    if t in ("int", "string"):
        return (lo + hi) // 2
    if t == "decimal":
        return (lo + hi) / 2
    return lo + (hi - lo) // 2  # date


def materialize(v: Any, t: str) -> Any:
    """Convert the internal value to what a tester types into the field."""
    return "a" * v if t == "string" else v


def unit_label(step: Any, t: str) -> str:
    if t == "date":
        return f"{step} day" + ("s" if step != 1 else "")
    if t == "string":
        return "1 char"
    return display(step)


def display(v: Any, max_len: int | None = None) -> str:
    """Human-readable form of a value. Special tokens make invisible values visible."""
    if v is None:
        return "<null>"
    if isinstance(v, bool):
        return "True" if v else "False"
    if isinstance(v, str):
        if v == "":
            return "<empty>"
        if v.strip() == "":
            return f"<whitespace x{len(v)}>"
        if max_len and len(v) > max_len:
            return f"{v[:max_len - 12]}... (len {len(v)})"
        return v
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, Decimal):
        return format(v, "f")
    return str(v)


def validate_spec(spec: FieldSpec) -> list[str]:
    """Return a list of friendly error messages (empty = OK)."""
    errs: list[str] = []
    nm = (spec.name or "").strip()
    if not nm:
        return ["A field has no name."]
    if spec.type not in FIELD_TYPES:
        return [f"{nm}: unknown type '{spec.type}'."]
    if spec.type in RANGE_TYPES:
        try:
            parse_range(spec)
        except SpecError as e:
            errs.append(str(e))
    elif spec.type == "enum":
        vals = [a for a in spec.allowed if str(a).strip()]
        if not vals:
            errs.append(f"{nm}: add at least one allowed value (comma separated).")
        elif len(set(vals)) != len(vals):
            errs.append(f"{nm}: allowed values contain duplicates.")
    return errs
