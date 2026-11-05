from hypothesis import given, settings, strategies as st

from core.pairwise import all_pairs, generate_pairwise, pair_coverage


def covers(rows, sizes, forb=()):
    c, t = pair_coverage(rows, sizes, forb)
    return c == t


def test_classic_three_by_three_by_three():
    rows = generate_pairwise([3, 3, 3])
    assert covers(rows, [3, 3, 3]) and len(rows) <= 12


def test_binary_four_params_is_small():
    rows = generate_pairwise([2, 2, 2, 2])
    assert covers(rows, [2] * 4) and len(rows) <= 6


def test_single_and_empty():
    assert generate_pairwise([]) == []
    assert generate_pairwise([3]) == [(0,), (1,), (2,)]


def test_deterministic():
    assert generate_pairwise([3, 4, 2, 5]) == generate_pairwise([3, 4, 2, 5])


def test_forbidden_pairs_never_appear():
    forb = [(0, 0, 1, 0)]
    rows = generate_pairwise([2, 2, 3], forb)
    assert all(not (r[0] == 0 and r[1] == 0) for r in rows)
    assert covers(rows, [2, 2, 3], forb)


@settings(max_examples=60, deadline=None)
@given(st.lists(st.integers(1, 5), min_size=2, max_size=6))
def test_property_full_pair_coverage(sizes):
    rows = generate_pairwise(sizes)
    assert covers(rows, sizes)
    assert len(rows) == len(set(rows))
    assert len(rows) <= max(1, len(all_pairs(sizes)))
