import random

import pytest
from hypothesis import given, settings, strategies as st

from core.decision_table import (TooManyCombinations, collapse, combo_key, expand, full_combos,
                                 full_rules, is_equivalent, pairwise_coverage, pairwise_rules,
                                 prune_constraints, rules_to_testcases, validate,
                                 validate_conditions)
from core.examples import login_example, shipping_example
from core.models import DONT_CARE, Condition, Rule
from core.values import SpecError


def test_login_reduction_numbers():
    p = login_example()
    full = full_rules(p.conditions, p.action_map, actions=p.actions)
    col = collapse(full, p.conditions)
    pw = pairwise_rules(p.conditions, p.action_map, actions=p.actions)
    assert (len(full), len(col)) == (16, 5)
    assert len(pw) <= 6
    assert is_equivalent(full, col, p.conditions)
    assert validate(full, p.conditions) == [] and validate(col, p.conditions) == []


def test_collapse_never_merges_different_actions():
    conds = [Condition("A"), Condition("B")]
    rules = [Rule("R1", {"A": "Y", "B": "Y"}, ["X"]), Rule("R2", {"A": "N", "B": "Y"}, ["Z"]),
             Rule("R3", {"A": "Y", "B": "N"}, ["X"]), Rule("R4", {"A": "N", "B": "N"}, ["Z"])]
    col = collapse(rules, conds)
    assert len(col) == 2
    assert {tuple(sorted(r.conditions.items())) for r in col} == {
        (("A", "Y"), ("B", DONT_CARE)), (("A", "N"), ("B", DONT_CARE))}
    assert is_equivalent(rules, col, conds)


def test_collapse_multivalue_needs_all_values():
    conds = [Condition("U", ["a", "b", "c"]), Condition("F")]
    rules = [Rule(f"R{i}", {"U": u, "F": f}, ["ok"] if u != "c" else ["no"])
             for i, (u, f) in enumerate([(u, f) for u in "abc" for f in "YN"], 1)]
    col = collapse(rules, conds)
    # F merges for each U; a/b cannot merge into U='-' because c has a different action
    assert len(col) == 3
    assert {r.conditions['U'] for r in col} == {'a', 'b', 'c'}
    assert is_equivalent(rules, col, conds)


@settings(max_examples=60, deadline=None)
@given(st.integers(0, 10_000), st.integers(2, 4), st.integers(1, 3))
def test_property_collapse_preserves_behaviour(seed, n_conds, n_actions):
    rnd = random.Random(seed)
    conds = [Condition(f"C{i}", ["v%d" % j for j in range(rnd.randint(2, 3))])
             for i in range(n_conds)]
    amap = {combo_key(conds, c): [f"A{rnd.randrange(n_actions)}"] for c in full_combos(conds)}
    full = full_rules(conds, amap)
    col = collapse(full, conds)
    assert len(col) <= len(full)
    assert is_equivalent(full, col, conds)
    assert validate(col, conds) == []


def test_validation_conflict_gap_incomplete():
    conds = [Condition("A"), Condition("B")]
    rules = [Rule("R1", {"A": "Y", "B": DONT_CARE}, ["X"]),
             Rule("R2", {"A": "Y", "B": "N"}, ["Z"]),     # overlaps R1 with a different action
             Rule("R3", {"A": "N", "B": "Y"}, [])]        # no action; (N,N) is a gap
    msgs = [(i.level, i.message) for i in validate(rules, conds)]
    levels = {m[0] for m in msgs}
    assert "error" in levels and "warning" in levels
    assert any("Conflict" in m for _, m in msgs)
    assert any("Gap" in m for _, m in msgs)
    assert any("no action" in m for _, m in msgs)


def test_duplicate_same_action_is_info():
    conds = [Condition("A")]
    rules = [Rule("R1", {"A": "Y"}, ["X"]), Rule("R2", {"A": "Y"}, ["X"]),
             Rule("R3", {"A": "N"}, ["X"])]
    issues = validate(rules, conds)
    assert [i.level for i in issues] == ["info"]


def test_constraints_exclude_combinations():
    conds = [Condition("Locked"), Condition("Login OK")]
    cons = [{"Locked": "Y", "Login OK": "Y"}]
    combos = full_combos(conds, cons)
    assert len(combos) == 3
    assert all(not (c["Locked"] == "Y" and c["Login OK"] == "Y") for c in combos)
    rules = full_rules(conds, {}, cons)
    assert not any("Gap" in i.message for i in validate(rules, conds, cons))


def test_pairwise_respects_constraints_and_coverage():
    p = shipping_example()
    cons = [{"Payment": "Cash on delivery", "Destination": "International"}]
    pw = pairwise_rules(p.conditions, p.action_map, cons, p.actions)
    assert all(not (r.conditions["Payment"] == "Cash on delivery"
                    and r.conditions["Destination"] == "International") for r in pw)
    c, t = pairwise_coverage(p.conditions, pw, cons)
    assert c == t
    assert len(pw) < 54


def test_too_many_combinations():
    conds = [Condition(f"C{i}", ["a", "b", "c"]) for i in range(10)]
    with pytest.raises(TooManyCombinations):
        full_combos(conds)
    assert pairwise_rules(conds, {})  # pairwise still works


def test_input_validation():
    assert validate_conditions([], ["x"])
    assert any("more than once" in e for e in validate_conditions(
        [Condition("A"), Condition("A")], ["x"]))
    assert any("duplicate" in e for e in validate_conditions([Condition("A", ["Y", "Y"])], ["x"]))
    assert any("reserved" in e for e in validate_conditions([Condition("A", ["-", "Y"])], ["x"]))
    assert any("action" in e for e in validate_conditions([Condition("A")], []))
    assert validate_conditions([Condition("A")], ["x"]) == []


def test_prune_constraints():
    conds = [Condition("A"), Condition("B")]
    keep = {"A": "Y", "B": "N"}
    assert prune_constraints(conds, [keep, {"A": "Y", "Z": "N"}, {"A": "Q", "B": "N"}]) == [keep]


def test_testcase_generation_from_rules():
    p = login_example()
    col = collapse(full_rules(p.conditions, p.action_map, actions=p.actions), p.conditions)
    cases = rules_to_testcases(col, "Decision table (collapsed)", "TC-LOGIN")
    assert cases[0].id == "TC-LOGIN-001"
    assert "any value" in cases[0].steps
    assert cases[0].source_rule.startswith("R")
    with pytest.raises(SpecError):
        rules_to_testcases(col, "x", step_template="{oops}")


def test_expand_counts():
    conds = [Condition("A"), Condition("B", ["1", "2", "3"])]
    r = [Rule("R1", {"A": DONT_CARE, "B": DONT_CARE}, ["x"])]
    assert len(expand(r, conds)) == 6
