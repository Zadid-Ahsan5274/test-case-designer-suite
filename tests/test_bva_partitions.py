from datetime import date
from decimal import Decimal

import pytest

from core.bva import range_boundaries
from core.combiner import generate_field_cases
from core.models import FieldSpec
from core.partitions import ep_classes, equivalence_partitions
from core.values import SpecError, validate_spec


def vals(spec, mode):
    return [c.value for c in range_boundaries(spec, mode)[0]]


def test_three_value_age():
    assert vals(FieldSpec("Age", "int", 18, 60), "3-value") == [17, 18, 19, 59, 60, 61]


def test_two_value_age():
    assert vals(FieldSpec("Age", "int", 18, 60), "2-value") == [17, 18, 60, 61]


def test_validity_flags():
    cases, _ = range_boundaries(FieldSpec("Age", "int", 18, 60))
    assert {c.value: c.valid for c in cases} == {17: False, 18: True, 19: True, 59: True,
                                                  60: True, 61: False}


def test_robust_contains_extremes_and_nominal():
    v = vals(FieldSpec("Age", "int", 18, 60), "robust")
    assert {0, -1, 39, 2147483647, -2147483648} <= set(v)


def test_min_equals_max_is_deduplicated():
    cases, _ = generate_field_cases(FieldSpec("X", "int", 5, 5))
    values = [c.value for c in cases if isinstance(c.value, int)]
    assert len(values) == len(set(values))
    merged = next(c for c in cases if c.value == 5)
    assert "Min" in merged.partition and "Max" in merged.partition


def test_decimal_step():
    v = vals(FieldSpec("P", "decimal", "0", "100", "0.5"), "3-value")
    assert v == [Decimal("-0.5"), Decimal("0"), Decimal("0.5"), Decimal("99.5"),
                 Decimal("100"), Decimal("100.5")]


def test_string_length_skips_negative():
    cases, notes = range_boundaries(FieldSpec("S", "string", 0, 5))
    assert [len(c.value) for c in cases] == [0, 1, 4, 5, 6]
    assert any("impossible" in n for n in notes)


def test_date_boundaries_and_leap_day():
    spec = FieldSpec("D", "date", "2024-01-01", "2024-12-31")
    assert vals(spec, "3-value")[0] == date(2023, 12, 31)
    assert date(2024, 2, 29) in vals(spec, "robust")


def test_enum_partitions():
    cases, _ = equivalence_partitions(FieldSpec("Tier", "enum", allowed=["Silver", "Gold"]))
    by = {c.partition: c for c in cases}
    assert by["Valid value: Gold"].valid and not by["Not in list"].valid
    assert not by["Case variant"].valid and by["Case variant"].value == "sILVER"
    assert not by["Empty"].valid


def test_optional_field_empty_is_valid():
    cases, _ = equivalence_partitions(FieldSpec("T", "int", 1, 9, required=False))
    assert all(c.valid for c in cases if c.partition in ("Empty", "Null / missing"))
    assert "Empty" not in ep_classes(FieldSpec("T", "int", 1, 9, required=False))


def test_bool_partitions():
    cases, _ = equivalence_partitions(FieldSpec("B", "bool"))
    assert [c.valid for c in cases[:3]] == [True, True, False]


@pytest.mark.parametrize("spec,msg", [
    (FieldSpec("A", "int", 10, 5), "greater than Max"),
    (FieldSpec("A", "int", "x", 5), "whole number"),
    (FieldSpec("A", "int", 1, 5, 0), "Step"),
    (FieldSpec("", "int", 1, 5), "no name"),
    (FieldSpec("A", "enum"), "allowed value"),
    (FieldSpec("A", "date", "2024-02-30", "2024-03-01"), "YYYY-MM-DD"),
    (FieldSpec("A", "string", -1, 5), "negative"),
])
def test_friendly_errors(spec, msg):
    errs = validate_spec(spec)
    assert errs and msg in errs[0]
    with pytest.raises(SpecError):
        generate_field_cases(spec)
