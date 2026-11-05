"""Module B: decision tables - full, collapsed, pairwise, validation, test cases."""
from __future__ import annotations

import itertools
import json
from typing import Iterable

from .models import DONT_CARE, Condition, GeneratedCase, Issue, Rule
from .pairwise import generate_pairwise, pair_coverage
from .values import SpecError

MAX_ROWS = 10_000
Constraint = dict[str, str]  # a forbidden combination, e.g. {"Account locked": "Y", "Login OK": "Y"}


class TooManyCombinations(Exception):
    """The full table would be too large; use pairwise instead."""

    def __init__(self, count: int, limit: int):
        super().__init__(f"The full table would have {count:,} rules (limit {limit:,}). "
                         "Switch to pairwise or reduce the number of values.")
        self.count, self.limit = count, limit


# ---------------------------------------------------------------- validation of input
def validate_conditions(conditions: list[Condition], actions: list[str]) -> list[str]:
    errs: list[str] = []
    if not conditions:
        return ["Add at least one condition."]
    names = [c.name.strip() for c in conditions]
    if any(not n for n in names):
        errs.append("Every condition needs a name.")
    for n in sorted({n for n in names if n and names.count(n) > 1}):
        errs.append(f"Condition name '{n}' is used more than once.")
    for c in conditions:
        vals = [v for v in c.values]
        if not vals:
            errs.append(f"Condition '{c.name}' needs at least one value.")
        elif len(set(vals)) != len(vals):
            errs.append(f"Condition '{c.name}' has duplicate values.")
        elif DONT_CARE in vals:
            errs.append(f"Condition '{c.name}': the value '{DONT_CARE}' is reserved for 'don't care'.")
    if not actions:
        errs.append("Add at least one action (expected outcome).")
    elif len(set(actions)) != len(actions):
        errs.append("Actions must be unique.")
    return errs


def prune_constraints(conditions: list[Condition], constraints: list[Constraint]) -> list[Constraint]:
    """Drop constraints that reference conditions / values that no longer exist."""
    vals = {c.name: set(c.values) for c in conditions}
    ok = []
    for con in constraints:
        if len(con) >= 2 and all(k in vals and v in vals[k] for k, v in con.items()):
            ok.append(con)
    return ok


def _violates(combo: dict[str, str], constraints: Iterable[Constraint]) -> bool:
    return any(all(combo.get(k) == v for k, v in con.items()) for con in constraints)


def combo_count(conditions: list[Condition]) -> int:
    n = 1
    for c in conditions:
        n *= max(len(c.values), 1)
    return n


def combo_key(conditions: list[Condition], combo: dict[str, str]) -> str:
    """Stable key used to store the user's action choices for a combination."""
    return json.dumps([combo[c.name] for c in conditions], ensure_ascii=False)


def _actions_for(conditions, combo, action_map, valid_actions):
    acts = list(action_map.get(combo_key(conditions, combo), []))
    if valid_actions is not None:
        acts = [a for a in valid_actions if a in acts]  # also fixes ordering
    return acts


# ---------------------------------------------------------------- table builders
def full_combos(conditions: list[Condition], constraints: list[Constraint] = (),
                max_rows: int = MAX_ROWS) -> list[dict[str, str]]:
    n = combo_count(conditions)
    if n > max_rows:
        raise TooManyCombinations(n, max_rows)
    names = [c.name for c in conditions]
    out = []
    for vals in itertools.product(*[c.values for c in conditions]):
        combo = dict(zip(names, vals))
        if not _violates(combo, constraints):
            out.append(combo)
    return out


def full_rules(conditions: list[Condition], action_map: dict[str, list[str]],
               constraints: list[Constraint] = (), actions: list[str] | None = None,
               max_rows: int = MAX_ROWS) -> list[Rule]:
    return [Rule(f"R{i}", combo, _actions_for(conditions, combo, action_map, actions))
            for i, combo in enumerate(full_combos(conditions, constraints, max_rows), 1)]


def pairwise_rules(conditions: list[Condition], action_map: dict[str, list[str]],
                   constraints: list[Constraint] = (), actions: list[str] | None = None
                   ) -> list[Rule]:
    names = [c.name for c in conditions]
    sizes = [len(c.values) for c in conditions]
    idx = {n: i for i, n in enumerate(names)}
    forbidden = []
    for con in constraints:
        if len(con) == 2:
            (ka, va), (kb, vb) = con.items()
            forbidden.append((idx[ka], conditions[idx[ka]].values.index(va),
                              idx[kb], conditions[idx[kb]].values.index(vb)))
    rows = generate_pairwise(sizes, forbidden)
    rules = []
    for tup in rows:
        combo = {c.name: c.values[i] for c, i in zip(conditions, tup)}
        if _violates(combo, constraints):  # constraints with 3+ items are filtered here
            continue
        rules.append(Rule(f"P{len(rules) + 1}", combo,
                          _actions_for(conditions, combo, action_map, actions)))
    return rules


def pairwise_coverage(conditions: list[Condition], rules: list[Rule],
                      constraints: list[Constraint] = ()) -> tuple[int, int]:
    sizes = [len(c.values) for c in conditions]
    idx_rows = [tuple(c.values.index(r.conditions[c.name]) for c in conditions) for r in rules]
    names = [c.name for c in conditions]
    forb = []
    for con in constraints:
        if len(con) == 2:
            (ka, va), (kb, vb) = con.items()
            ia, ib = names.index(ka), names.index(kb)
            forb.append((ia, conditions[ia].values.index(va), ib, conditions[ib].values.index(vb)))
    return pair_coverage(idx_rows, sizes, forb)


# ---------------------------------------------------------------- collapse / expand
def collapse(rules: list[Rule], conditions: list[Condition]) -> list[Rule]:
    """Merge rules with identical actions that differ only in one condition covering all
    of that condition's values, replacing it with '-' (don't care). Repeats to a fixpoint.
    Never merges rules whose actions differ, so no information is lost."""
    names = [c.name for c in conditions]
    domain = {c.name: set(c.values) for c in conditions}
    work = [(dict(r.conditions), list(r.actions), list(r.sources or [r.id])) for r in rules]
    changed = True
    while changed:
        changed = False
        for cname in names:
            buckets: dict[tuple, list[int]] = {}
            for i, (cond, acts, _) in enumerate(work):
                key = (frozenset(acts), tuple(cond[n] for n in names if n != cname))
                buckets.setdefault(key, []).append(i)
            drop: set[int] = set()
            for members in buckets.values():
                if len(members) < 2:
                    continue
                present = {work[i][0][cname] for i in members}
                if DONT_CARE in present or present >= domain[cname]:
                    head = members[0]
                    cond, acts, src = work[head]
                    cond[cname] = DONT_CARE
                    for i in members[1:]:
                        src += [s for s in work[i][2] if s not in src]
                        drop.add(i)
                    changed = True
            if drop:
                work = [w for i, w in enumerate(work) if i not in drop]
    return [Rule(f"R{n}", cond, acts, src) for n, (cond, acts, src) in enumerate(work, 1)]


def expand(rules: list[Rule], conditions: list[Condition]) -> dict[tuple[str, ...], list[int]]:
    """Map every concrete combination to the indexes of the rules that cover it."""
    out: dict[tuple[str, ...], list[int]] = {}
    for ri, r in enumerate(rules):
        choices = [c.values if r.conditions[c.name] == DONT_CARE else [r.conditions[c.name]]
                   for c in conditions]
        for combo in itertools.product(*choices):
            out.setdefault(combo, []).append(ri)
    return out


def is_equivalent(a: list[Rule], b: list[Rule], conditions: list[Condition]) -> bool:
    """True if both tables map every combination to the same set of actions."""
    ea, eb = expand(a, conditions), expand(b, conditions)
    if ea.keys() != eb.keys():
        return False
    for k in ea:
        sa = {frozenset(a[i].actions) for i in ea[k]}
        sb = {frozenset(b[i].actions) for i in eb[k]}
        if sa != sb or len(sa) != 1:
            return False
    return True


# ---------------------------------------------------------------- validation
def validate(rules: list[Rule], conditions: list[Condition],
             constraints: list[Constraint] = (), max_expand: int = MAX_ROWS) -> list[Issue]:
    issues: list[Issue] = []
    empty = [r.id for r in rules if not r.actions]
    if empty:
        issues.append(Issue("warning", f"{len(empty)} rule(s) have no action selected: "
                            f"{_short(empty)}.", empty))

    total = 0
    for r in rules:
        sz = 1
        for c in conditions:
            sz *= len(c.values) if r.conditions[c.name] == DONT_CARE else 1
        total += sz
    if total > max_expand:
        issues.append(Issue("info", "Table too large for conflict / gap analysis "
                                    f"({total:,} combinations)."))
        return issues

    cover = expand(rules, conditions)
    names = [c.name for c in conditions]
    conflicts, dups = [], []
    for combo, idxs in cover.items():
        if len(idxs) < 2:
            continue
        action_sets = {frozenset(rules[i].actions) for i in idxs}
        ids = [rules[i].id for i in idxs]
        desc = ", ".join(f"{n}={v}" for n, v in zip(names, combo))
        (conflicts if len(action_sets) > 1 else dups).append((desc, ids))
    for desc, ids in conflicts[:20]:
        issues.append(Issue("error", f"Conflict: rules {', '.join(ids)} cover the same case "
                                     f"({desc}) but give different actions.", ids))
    if len(conflicts) > 20:
        issues.append(Issue("error", f"... and {len(conflicts) - 20} more conflicts."))
    if dups:
        ids = sorted({i for _, x in dups for i in x})
        issues.append(Issue("info", f"{len(dups)} combination(s) are covered by more than one "
                                    f"rule with the same action (duplicates): {_short(ids)}.", ids))

    gaps = [c for c in full_combos(conditions, constraints, max_expand)
            if tuple(c[n] for n in names) not in cover]
    if gaps:
        ex = "; ".join(", ".join(f"{k}={v}" for k, v in g.items()) for g in gaps[:3])
        issues.append(Issue("warning", f"Gap: {len(gaps)} possible combination(s) are not covered "
                                       f"by any rule, e.g. {ex}."))
    return issues


def _short(items: list[str], n: int = 8) -> str:
    return ", ".join(items[:n]) + (f", ... (+{len(items) - n})" if len(items) > n else "")


# ---------------------------------------------------------------- test cases
DEFAULT_STEP_TEMPLATE = "Set {condition} = {value}"


def rules_to_testcases(rules: list[Rule], technique: str, prefix: str = "TC",
                       step_template: str = DEFAULT_STEP_TEMPLATE,
                       final_step: str = "Execute the scenario and observe the result"
                       ) -> list[GeneratedCase]:
    pre = (prefix or "").strip().rstrip("-") or "TC"
    try:
        step_template.format(condition="x", value="y")
    except (KeyError, IndexError, ValueError):
        raise SpecError("Step template may only use {condition} and {value}.") from None
    cases = []
    for n, r in enumerate(rules, 1):
        lines = []
        for cond, val in r.conditions.items():
            if val == DONT_CARE:
                lines.append(f"{cond}: any value (not relevant for this rule)")
            else:
                lines.append(step_template.format(condition=cond, value=val))
        lines.append(final_step)
        steps = "\n".join(f"{i}. {s}" for i, s in enumerate(lines, 1))
        expected = " + ".join(r.actions) if r.actions else "(no action defined)"
        src = ", ".join(r.sources) if r.sources else r.id
        cases.append(GeneratedCase(
            id=f"{pre}-{n:03d}", inputs=dict(r.conditions), expected=expected,
            technique=technique, title=f"{r.id}: {expected}", steps=steps, source_rule=src))
    return cases
