"""Equivalence Partitioning."""
from __future__ import annotations

from .models import RANGE_TYPES, Case, FieldSpec
from .values import SpecError, materialize, midpoint, parse_range, shift


def _empty_cases(spec: FieldSpec) -> list[Case]:
    valid = not spec.required
    why = "optional field may be left empty" if valid else "required field must not be empty"
    return [
        Case("", "EP-empty", "Empty", valid, why),
        Case(None, "EP-null", "Null / missing", valid, why),
    ]


def _range_ep(spec: FieldSpec) -> tuple[list[Case], list[str]]:
    lo, hi, step = parse_range(spec)
    t, nm = spec.type, spec.name
    notes: list[str] = []

    cases = [Case(materialize(midpoint(lo, hi, t), t), "EP-valid", "Valid (nominal)", True,
                  "representative value from the valid partition")]
    low, high = shift(lo, -10, step, t), shift(hi, 10, step, t)
    if low is None or (t == "string" and low < 0):
        notes.append(f"{nm}: 'below range' partition skipped (not representable).")
    else:
        cases.append(Case(materialize(low, t), "EP-invalid", "Invalid: below range", False,
                          "representative value from the below-range partition"))
    if high is None:
        notes.append(f"{nm}: 'above range' partition skipped (not representable).")
    else:
        cases.append(Case(materialize(high, t), "EP-invalid", "Invalid: above range", False,
                          "representative value from the above-range partition"))

    if t == "int":
        bad = [("abc", "Invalid type: letters"), ("12.5", "Invalid type: decimal for integer field"),
               ("@#$", "Invalid type: special characters"), ("   ", "Invalid type: whitespace only")]
        cases += [Case(v, "EP-invalid", p, False, "wrong data type") for v, p in bad]
    elif t == "decimal":
        bad = [("abc", "Invalid type: letters"), ("1.2.3", "Invalid type: malformed number"),
               ("@#$", "Invalid type: special characters"), ("   ", "Invalid type: whitespace only")]
        cases += [Case(v, "EP-invalid", p, False, "wrong data type") for v, p in bad]
    elif t == "date":
        bad = [("2023-02-30", "Invalid calendar date"), ("not-a-date", "Invalid type: text"),
               ("31/12/2024", "Invalid format (expected YYYY-MM-DD)")]
        cases += [Case(v, "EP-invalid", p, False, "wrong data type / format") for v, p in bad]
    elif t == "string":
        n = max(lo, 1)
        cases.append(Case(" " * n, "EP-invalid", "Whitespace only", not spec.required,
                          "whitespace-only input should be treated as blank (assumption)"))
    cases += _empty_cases(spec)
    return cases, notes


def _enum_ep(spec: FieldSpec) -> tuple[list[Case], list[str]]:
    allowed = [str(a) for a in spec.allowed if str(a).strip()]
    cases = [Case(v, "EP-valid", f"Valid value: {v}", True, "member of the allowed list")
             for v in allowed]
    junk = "INVALID_VALUE"
    while junk in allowed:
        junk += "_"
    cases.append(Case(junk, "EP-invalid", "Not in list", False, "value outside the allowed list"))
    for v in allowed:
        variant = v.swapcase()
        if variant != v and variant not in allowed:
            cases.append(Case(variant, "EP-invalid", "Case variant", False,
                              "case-sensitivity check (assumes case-sensitive matching)"))
            break
    cases += _empty_cases(spec)
    return cases, []


def _bool_ep(spec: FieldSpec) -> tuple[list[Case], list[str]]:
    cases = [
        Case(True, "EP-valid", "Valid: True", True, "valid boolean"),
        Case(False, "EP-valid", "Valid: False", True, "valid boolean"),
        Case("maybe", "EP-invalid", "Invalid: not a boolean", False, "wrong data type"),
    ]
    return cases + _empty_cases(spec), []


def equivalence_partitions(spec: FieldSpec) -> tuple[list[Case], list[str]]:
    if spec.type in RANGE_TYPES:
        return _range_ep(spec)
    if spec.type == "enum":
        return _enum_ep(spec)
    if spec.type == "bool":
        return _bool_ep(spec)
    raise SpecError(f"{spec.name}: unknown type '{spec.type}'.")


def ep_classes(spec: FieldSpec) -> list[str]:
    """Short partition names, usable as decision-table condition values."""
    if spec.type in RANGE_TYPES:
        base = ["Valid", "Below range", "Above range", "Wrong type"]
    elif spec.type == "enum":
        base = ["Valid", "Not in list"]
    else:
        base = ["Valid", "Invalid"]
    return base + (["Empty"] if spec.required else [])
