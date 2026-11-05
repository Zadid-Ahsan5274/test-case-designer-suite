"""Module A: turn field definitions into multi-field test cases."""
from __future__ import annotations

from dataclasses import dataclass, field

from .bva import range_boundaries
from .models import RANGE_TYPES, Case, FieldSpec, GeneratedCase
from .pairwise import generate_pairwise
from .partitions import equivalence_partitions
from .values import SpecError, display, validate_spec

STRATEGIES = {
    "vary_one": "One field varied at a time (others stay valid) - best for isolating failures",
    "pairwise_valid": "Valid values only, combined pairwise - fewer cases for multi-field forms",
    "per_field": "Per-field only (no combining)",
}


@dataclass
class Generation:
    cases: list[GeneratedCase]
    notes: list[str] = field(default_factory=list)
    field_cases: dict[str, list[Case]] = field(default_factory=dict)


def _key(v):
    from decimal import Decimal
    if isinstance(v, Decimal):
        return ("decimal", format(v.normalize(), "f"))
    return (type(v).__name__, repr(v))


def _uniq(items: list[str]) -> list[str]:
    seen, out = set(), []
    for i in items:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def merge_cases(cases: list[Case]) -> list[Case]:
    """De-duplicate identical values and merge their technique / partition / rationale."""
    order: dict[tuple, list[Case]] = {}
    for c in cases:
        order.setdefault(_key(c.value), []).append(c)
    merged = []
    for group in order.values():
        first = group[0]
        merged.append(Case(
            value=first.value,
            technique=", ".join(_uniq([g.technique for g in group])),
            partition=" / ".join(_uniq([g.partition for g in group])),
            valid=first.valid,
            rationale="; ".join(_uniq([g.rationale for g in group])),
        ))
    return merged


def generate_field_cases(spec: FieldSpec, mode: str = "3-value") -> tuple[list[Case], list[str]]:
    errs = validate_spec(spec)
    if errs:
        raise SpecError(" ".join(errs))
    notes: list[str] = []
    cases: list[Case] = []
    if spec.type in RANGE_TYPES:
        bva, n1 = range_boundaries(spec, mode)
        cases += bva
        notes += n1
    ep, n2 = equivalence_partitions(spec)
    cases += ep
    notes += n2
    return merge_cases(cases), notes


def baseline_case(cases: list[Case]) -> Case:
    for c in cases:
        if c.valid and "EP-valid" in c.technique:
            return c
    for c in cases:
        if c.valid:
            return c
    raise SpecError("No valid value could be generated for a field.")


def _expected(spec: FieldSpec, valid: bool) -> str:
    return "Accept" if valid else (spec.on_invalid.strip() or "Reject with error")


def _steps(inputs: dict) -> str:
    lines = [f"{i}. Set {k} = {display(v)}" for i, (k, v) in enumerate(inputs.items(), 1)]
    lines.append(f"{len(lines) + 1}. Submit the form")
    return "\n".join(lines)


def _clean_prefix(prefix: str) -> str:
    p = (prefix or "").strip().rstrip("-")
    return p or "TC"


def build_testcases(specs: list[FieldSpec], mode: str = "3-value", strategy: str = "vary_one",
                    prefix: str = "TC") -> Generation:
    if not specs:
        raise SpecError("Add at least one field to generate test cases.")
    if strategy not in STRATEGIES:
        raise SpecError(f"Unknown strategy '{strategy}'.")
    names = [s.name.strip() for s in specs]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        raise SpecError(f"Field names must be unique (duplicate: {', '.join(dupes)}).")
    for s in specs:
        s.name = s.name.strip()

    notes: list[str] = []
    field_cases: dict[str, list[Case]] = {}
    errors: list[str] = []
    for s in specs:
        try:
            cs, n = generate_field_cases(s, mode)
            field_cases[s.name] = cs
            notes += n
        except SpecError as e:
            errors.append(str(e))
    if errors:
        raise SpecError("\n".join(errors))

    pre = _clean_prefix(prefix)
    out: list[GeneratedCase] = []

    def new(inputs, expected, technique, partition, rationale, fld, title) -> None:
        out.append(GeneratedCase(
            id=f"{pre}-{len(out) + 1:03d}", inputs=inputs, expected=expected,
            technique=technique, partition=partition, rationale=rationale,
            field=fld, title=title, steps=_steps(inputs)))

    if strategy == "vary_one":
        base = {s.name: baseline_case(field_cases[s.name]) for s in specs}
        base_inputs = {n: c.value for n, c in base.items()}
        new(dict(base_inputs), "Accept", "Baseline", "All fields valid",
            "baseline: every field holds a valid nominal value", None,
            "Baseline - all fields valid")
        for s in specs:
            for c in field_cases[s.name]:
                if c is base[s.name]:
                    continue
                inputs = dict(base_inputs)
                inputs[s.name] = c.value
                new(inputs, _expected(s, c.valid), c.technique, c.partition, c.rationale,
                    s.name, f"{s.name}: {c.partition}")
    elif strategy == "per_field":
        for s in specs:
            for c in field_cases[s.name]:
                new({s.name: c.value}, _expected(s, c.valid), c.technique, c.partition,
                    c.rationale, s.name, f"{s.name}: {c.partition}")
    else:  # pairwise_valid
        valid = {s.name: [c for c in field_cases[s.name] if c.valid] for s in specs}
        sizes = [len(valid[s.name]) for s in specs]
        full = 1
        for z in sizes:
            full *= z
        rows = generate_pairwise(sizes)
        notes.append(f"Pairwise: {full:,} full valid combinations reduced to {len(rows)}.")
        for n, idx in enumerate(rows, 1):
            chosen = {s.name: valid[s.name][i] for s, i in zip(specs, idx)}
            inputs = {k: c.value for k, c in chosen.items()}
            part = "; ".join(f"{k}: {c.partition}" for k, c in chosen.items())
            new(inputs, "Accept", "Pairwise (valid values)", part,
                "every pair of valid values appears together at least once", None,
                f"Valid combination {n}")
    return Generation(out, notes, field_cases)
