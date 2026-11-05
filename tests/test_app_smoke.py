"""Run every Streamlit page headlessly and make sure nothing raises."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
PAGES = ["app.py", "pages/1_Boundary_Partition.py", "pages/2_Decision_Table.py",
         "pages/3_About_Examples.py"]


@pytest.mark.parametrize("page", PAGES)
def test_page_renders(page):
    at = AppTest.from_file(str(ROOT / page), default_timeout=30).run()
    assert not at.exception, [e.value for e in at.exception]


def test_module_a_example_buttons_and_bad_input():
    at = AppTest.from_file(str(ROOT / "pages/1_Boundary_Partition.py"), default_timeout=30).run()
    assert not at.exception
    assert len(at.dataframe) >= 1
    next(b for b in at.button if "Registration" in b.label).click()
    at.run()
    assert not at.exception
    assert len(at.dataframe) >= 2


def test_module_b_load_checkout_example():
    at = AppTest.from_file(str(ROOT / "pages/2_Decision_Table.py"), default_timeout=30).run()
    assert not at.exception
    next(b for b in at.button if "Checkout" in b.label).click()
    at.run()
    assert not at.exception
    assert any("Pairwise" in s.value for s in at.success)
