import pytest

from core.combiner import build_testcases
from core.examples import registration_example
from core.models import FieldSpec
from core.values import SpecError


def two_fields():
    return [FieldSpec("Age", "int", 18, 60), FieldSpec("Tier", "enum", allowed=["Gold", "Silver"])]


def test_vary_one_count_and_baseline():
    gen = build_testcases(two_fields(), "3-value", "vary_one", "TC")
    expected = 1 + sum(len(v) - 1 for v in gen.field_cases.values())
    assert len(gen.cases) == expected
    base = gen.cases[0]
    assert base.expected == "Accept" and base.technique == "Baseline"
    assert base.inputs == {"Age": 39, "Tier": "Gold"}


def test_vary_one_changes_exactly_one_field():
    gen = build_testcases(two_fields(), "3-value", "vary_one", "TC")
    base = gen.cases[0].inputs
    for c in gen.cases[1:]:
        diff = [k for k in base if base[k] != c.inputs[k]]
        assert diff == [c.field]


def test_invalid_input_is_rejected_valid_accepted():
    gen = build_testcases(two_fields(), "3-value", "vary_one", "TC")
    by = {(c.field, c.partition): c for c in gen.cases if c.field}
    assert by[("Age", "Just below min")].expected == "Reject with error"
    assert by[("Age", "Min")].expected == "Accept"


def test_ids_prefix_and_unique():
    gen = build_testcases(two_fields(), prefix="TC-LOGIN-")
    ids = [c.id for c in gen.cases]
    assert ids[0] == "TC-LOGIN-001" and len(ids) == len(set(ids))


def test_per_field_only_has_one_input():
    gen = build_testcases(two_fields(), strategy="per_field")
    assert all(len(c.inputs) == 1 for c in gen.cases)


def test_pairwise_valid_reduces_and_all_accept():
    specs = registration_example().fields
    gen = build_testcases(specs, "3-value", "pairwise_valid")
    assert all(c.expected == "Accept" for c in gen.cases)
    assert any("reduced" in n for n in gen.notes)
    assert len(gen.cases) < 100


def test_errors_are_friendly():
    with pytest.raises(SpecError, match="at least one field"):
        build_testcases([])
    with pytest.raises(SpecError, match="unique"):
        build_testcases([FieldSpec("A", "int", 1, 2), FieldSpec("A", "int", 1, 2)])
    with pytest.raises(SpecError, match="greater than Max"):
        build_testcases([FieldSpec("A", "int", 9, 2)])


def test_all_example_modes_generate():
    for mode in ("2-value", "3-value", "robust"):
        for strat in ("vary_one", "pairwise_valid", "per_field"):
            assert build_testcases(registration_example().fields, mode, strat).cases
