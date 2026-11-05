"""Data models shared by the whole app."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

FIELD_TYPES = ("int", "decimal", "string", "date", "enum", "bool")
RANGE_TYPES = ("int", "decimal", "string", "date")

TYPE_HELP = {
    "int": "Whole number. Min/Max are the allowed values.",
    "decimal": "Decimal number. Min/Max are values; Step is the precision (default 0.01).",
    "string": "Text. Min/Max are the allowed LENGTH in characters.",
    "date": "Date. Min/Max in YYYY-MM-DD; Step is in days.",
    "enum": "List of allowed values. Fill 'Allowed values' (comma separated).",
    "bool": "True / False.",
}

DONT_CARE = "-"  # marker used in collapsed decision tables


@dataclass
class FieldSpec:
    """One input field to analyse with BVA / Equivalence Partitioning."""

    name: str
    type: str = "int"
    min: Any = None
    max: Any = None
    step: Any = None
    allowed: list[str] = field(default_factory=list)
    required: bool = True
    on_invalid: str = "Reject with error"


@dataclass
class Case:
    """One candidate value for a single field."""

    value: Any
    technique: str
    partition: str
    valid: bool
    rationale: str


@dataclass
class GeneratedCase:
    """A finished test case (used by both modules)."""

    id: str
    inputs: dict[str, Any]
    expected: str
    technique: str
    partition: str = ""
    rationale: str = ""
    field: str | None = None
    title: str = ""
    steps: str = ""
    source_rule: str = ""


@dataclass
class Condition:
    """A decision-table condition and the values it can take."""

    name: str
    values: list[str] = field(default_factory=lambda: ["Y", "N"])


@dataclass
class Rule:
    """A decision-table rule (one column of the classic table)."""

    id: str
    conditions: dict[str, str]
    actions: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)


@dataclass
class Issue:
    """A validation finding for a decision table."""

    level: str  # "error" | "warning" | "info"
    message: str
    rules: list[str] = field(default_factory=list)
