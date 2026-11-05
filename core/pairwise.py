"""Deterministic greedy all-pairs (pairwise) generator - no external dependency."""
from __future__ import annotations

from typing import Iterable

Forbidden = Iterable[tuple[int, int, int, int]]  # (param_i, value_i, param_j, value_j)


def _norm(i: int, vi: int, j: int, vj: int) -> tuple[int, int, int, int]:
    return (i, vi, j, vj) if i < j else (j, vj, i, vi)


def all_pairs(sizes: list[int], forbidden: Forbidden = ()) -> set[tuple[int, int, int, int]]:
    n = len(sizes)
    forb = {_norm(*f) for f in forbidden}
    return {
        (i, vi, j, vj)
        for i in range(n) for j in range(i + 1, n)
        for vi in range(sizes[i]) for vj in range(sizes[j])
    } - forb


def generate_pairwise(sizes: list[int], forbidden: Forbidden = ()) -> list[tuple[int, ...]]:
    """Rows of value indices covering every allowed pair of values at least once.

    sizes[k] is the number of values of parameter k. `forbidden` lists value pairs that
    must never appear together. Output is deterministic.
    """
    n = len(sizes)
    if n == 0:
        return []
    if any(s <= 0 for s in sizes):
        raise ValueError("Every parameter needs at least one value.")
    if n == 1:
        return [(v,) for v in range(sizes[0])]

    forb = {_norm(*f) for f in forbidden}
    uncovered = all_pairs(sizes, forb)
    rows: list[tuple[int, ...]] = []

    while uncovered:
        i, vi, j, vj = min(uncovered)
        row: list[int | None] = [None] * n
        row[i], row[j] = vi, vj
        ok = True
        for k in (k for k in range(n) if k not in (i, j)):
            best, best_gain = None, -1
            for v in range(sizes[k]):
                if any(row[m] is not None and _norm(m, row[m], k, v) in forb for m in range(n)):
                    continue
                gain = sum(1 for m in range(n)
                           if row[m] is not None and _norm(m, row[m], k, v) in uncovered)
                if gain > best_gain:
                    best, best_gain = v, gain
            if best is None:  # constraints leave no legal value: give up on this pair
                ok = False
                break
            row[k] = best
        if not ok:
            uncovered.discard((i, vi, j, vj))
            continue
        final = tuple(int(x) for x in row)  # type: ignore[arg-type]
        rows.append(final)
        for a in range(n):
            for b in range(a + 1, n):
                uncovered.discard((a, final[a], b, final[b]))
    return rows


def pair_coverage(rows: list[tuple[int, ...]], sizes: list[int],
                  forbidden: Forbidden = ()) -> tuple[int, int]:
    """(covered, total) number of allowed value pairs."""
    total = all_pairs(sizes, forbidden)
    covered = set()
    for r in rows:
        for a in range(len(r)):
            for b in range(a + 1, len(r)):
                covered.add((a, r[a], b, r[b]))
    return len(covered & total), len(total)
