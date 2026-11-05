import ast
import csv
import io
import json

import pytest
from openpyxl import load_workbook

from core.combiner import build_testcases
from core.decision_table import collapse, full_rules, rules_to_testcases
from core.examples import login_example, registration_example
from core.exporters import (rows_module_a, rows_module_b, to_csv, to_gherkin, to_json,
                            to_markdown, to_pytest, to_testrail_csv, to_xlsx)
from core.models import FieldSpec
from core.project import ProjectError, project_from_json, project_to_json


@pytest.fixture
def gen():
    return build_testcases(registration_example().fields, "robust", "vary_one", "TC-REG")


def test_csv_roundtrip(gen):
    rows = rows_module_a(gen.cases)
    back = list(csv.DictReader(io.StringIO(to_csv(rows).decode("utf-8-sig"))))
    assert len(back) == len(rows) and back[0]["TC ID"] == "TC-REG-001"


def test_json_markdown(gen):
    rows = rows_module_a(gen.cases)
    assert json.loads(to_json(rows))[0]["TC ID"] == "TC-REG-001"
    md = to_markdown(rows)
    assert md.splitlines()[0].startswith("| TC ID") and len(md.splitlines()) == len(rows) + 2


def test_xlsx_roundtrip_and_formula_safety():
    rows = [{"A": "=1+1", "B": "@#$"}, {"A": "-5", "B": "ok"}]
    ws = load_workbook(io.BytesIO(to_xlsx({"Data": rows})))["Data"]
    assert [c.value for c in ws[1]] == ["A", "B"]
    assert ws["A2"].value == "=1+1" and ws["A2"].data_type == "s"
    assert ws["A3"].value == "-5"


def test_gherkin_and_pytest_are_valid(gen):
    g = to_gherkin(gen.cases, "Registration")
    assert g.startswith("Feature: Registration") and 'Then the result should be "Accept"' in g
    code = to_pytest(gen.cases, "Registration form")
    ast.parse(code)
    assert "def test_registration_form(" in code


def test_pytest_executes_skeleton_with_param_names():
    cases = build_testcases([FieldSpec("Date of birth", "date", "2000-01-01", "2001-01-01"),
                             FieldSpec("1st name", "string", 1, 3)], "2-value").cases
    code = to_pytest(cases)
    ast.parse(code)
    assert "date_of_birth" in code and "p_1st_name" in code


def test_module_b_exports():
    p = login_example()
    col = collapse(full_rules(p.conditions, p.action_map, actions=p.actions), p.conditions)
    cases = rules_to_testcases(col, "Decision table (collapsed)", "TC-LOGIN")
    rows = rows_module_b(cases)
    assert "any" in rows[0]["Preconditions"]
    g = to_gherkin(cases, "Login", ["-"])
    assert '"-"' not in g
    ast.parse(to_pytest(cases, "login", ["-"]))
    assert b"Test Case (Steps)" in to_testrail_csv(cases)


def test_project_roundtrip():
    p = login_example()
    p.fields = registration_example().fields
    q = project_from_json(project_to_json(p))
    assert q.conditions == p.conditions and q.action_map == p.action_map
    assert q.fields == p.fields and q.name == p.name


def test_project_errors():
    with pytest.raises(ProjectError):
        project_from_json("not json")
    with pytest.raises(ProjectError):
        project_from_json("[1,2]")
    with pytest.raises(ProjectError):
        project_from_json(json.dumps({"version": 99}))
    assert project_from_json("{}").bva_mode == "3-value"


def test_example_files_load():
    from pathlib import Path
    for f in (Path(__file__).parents[1] / "examples").glob("*.json"):
        project_from_json(f.read_text())
