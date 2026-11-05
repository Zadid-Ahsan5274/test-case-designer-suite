"""Export test cases to CSV, Excel, JSON, Markdown, Gherkin, pytest and TestRail-style CSV."""
from __future__ import annotations

import csv
import io
import json
import re
from datetime import date
from decimal import Decimal
from typing import Any, Iterable

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .models import GeneratedCase
from .values import display


# ---------------------------------------------------------------- row builders
def rows_module_a(cases: list[GeneratedCase], max_len: int | None = None) -> list[dict]:
    rows = []
    for c in cases:
        if c.field:
            inp = display(c.inputs.get(c.field), max_len)
            others = "; ".join(f"{k}={display(v, max_len)}" for k, v in c.inputs.items()
                               if k != c.field)
        else:
            inp = "-"
            others = "; ".join(f"{k}={display(v, max_len)}" for k, v in c.inputs.items())
        rows.append({
            "TC ID": c.id, "Field": c.field or "(combination)", "Technique": c.technique,
            "Partition": c.partition, "Input Value": inp, "Other Fields' Values": others,
            "Expected Result": c.expected, "Rationale": c.rationale,
        })
    return rows


def rows_module_b(cases: list[GeneratedCase]) -> list[dict]:
    return [{
        "TC ID": c.id, "Title": c.title,
        "Preconditions": "; ".join(f"{k} = {'any' if v == '-' else v}" for k, v in c.inputs.items()),
        "Steps": c.steps, "Expected Result": c.expected,
        "Source Rule": c.source_rule, "Technique": c.technique,
    } for c in cases]


def _headers(rows: list[dict]) -> list[str]:
    heads: list[str] = []
    for r in rows:
        for k in r:
            if k not in heads:
                heads.append(k)
    return heads


# ---------------------------------------------------------------- tabular formats
def to_csv(rows: list[dict]) -> bytes:
    """UTF-8 with BOM so Excel opens it correctly."""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=_headers(rows), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


def to_json(rows: list[dict]) -> str:
    return json.dumps(rows, indent=2, ensure_ascii=False, default=str)


def to_markdown(rows: list[dict]) -> str:
    if not rows:
        return ""
    heads = _headers(rows)

    def esc(v: Any) -> str:
        return str(v if v is not None else "").replace("|", "\\|").replace("\n", "<br>")

    lines = ["| " + " | ".join(heads) + " |", "|" + "|".join("---" for _ in heads) + "|"]
    lines += ["| " + " | ".join(esc(r.get(h, "")) for h in heads) + " |" for r in rows]
    return "\n".join(lines) + "\n"


def _sheet_name(name: str) -> str:
    return re.sub(r"[\[\]:*?/\\]", "-", name)[:31] or "Sheet"


def to_xlsx(sheets: dict[str, list[dict]]) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    head_fill = PatternFill("solid", fgColor="1F4E79")
    for name, rows in sheets.items():
        ws = wb.create_sheet(_sheet_name(name))
        heads = _headers(rows)
        for ci, h in enumerate(heads, 1):
            c = ws.cell(row=1, column=ci, value=h)
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = head_fill
        for ri, r in enumerate(rows, 2):
            for ci, h in enumerate(heads, 1):
                v = r.get(h, "")
                cell = ws.cell(row=ri, column=ci, value=v)
                if isinstance(v, str):
                    cell.alignment = Alignment(wrap_text=True, vertical="top")
                    if v.startswith(("=", "+", "-", "@")):
                        cell.data_type = "s"  # never let Excel treat test data as a formula
        for ci, h in enumerate(heads, 1):
            longest = max([len(str(h))] + [max(len(p) for p in str(r.get(h, "")).split("\n") or [""])
                                           for r in rows])
            ws.column_dimensions[get_column_letter(ci)].width = min(max(longest + 2, 10), 60)
        ws.freeze_panes = "A2"
        if heads and rows:
            ws.auto_filter.ref = ws.dimensions
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def to_testrail_csv(cases: list[GeneratedCase], section: str = "Test Case Designer") -> bytes:
    """Generic 'steps + expected' CSV that TestRail / Zephyr / Xray importers can map."""
    rows = [{
        "Title": c.title or c.id, "Section": section, "Template": "Test Case (Steps)",
        "Type": "Functional", "Priority": "Medium",
        "Preconditions": "; ".join(f"{k} = {display(v)}" for k, v in c.inputs.items()),
        "Steps": c.steps, "Expected Result": c.expected, "References": c.id,
    } for c in cases]
    return to_csv(rows)


# ---------------------------------------------------------------- code-ish formats
def _q(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def to_gherkin(cases: list[GeneratedCase], feature: str = "Generated scenarios",
               skip_values: Iterable[str] = ()) -> str:
    skip = set(skip_values)
    out = [f"Feature: {feature}", ""]
    for c in cases:
        out.append(f"  Scenario: {c.id} - {c.title or c.technique}")
        first = True
        for k, v in c.inputs.items():
            if isinstance(v, str) and v in skip:
                continue
            out.append(f'    {"Given" if first else "And"} "{_q(k)}" is "{_q(display(v))}"')
            first = False
        if first:
            out.append("    Given the system is in its default state")
        out.append("    When the scenario is executed")
        out.append(f'    Then the result should be "{_q(c.expected)}"')
        out.append("")
    return "\n".join(out)


def _ident(name: str, used: set[str]) -> str:
    base = re.sub(r"\W+", "_", name).strip("_").lower() or "param"
    if base[0].isdigit():
        base = "p_" + base
    ident, n = base, 2
    while ident in used:
        ident, n = f"{base}_{n}", n + 1
    used.add(ident)
    return ident


def _literal(v: Any) -> str:
    if isinstance(v, (Decimal, date)):
        return repr(str(v))
    return repr(v)


def to_pytest(cases: list[GeneratedCase], test_name: str = "scenario",
              skip_values: Iterable[str] = ()) -> str:
    skip = set(skip_values)
    keys: list[str] = []
    for c in cases:
        for k in c.inputs:
            if k not in keys:
                keys.append(k)
    used = {"case_id", "expected"}
    idents = {k: _ident(k, used) for k in keys}
    params = ", ".join(["case_id", *idents.values(), "expected"])
    fn = _ident(test_name, set()) if test_name else "scenario"
    lines = [
        '"""Generated by Test Case Designer - connect `system_under_test` to your application."""',
        "import pytest", "", "",
        "def system_under_test(**inputs):",
        '    """TODO: call your API / UI driver and return "Accept" or the error/outcome text."""',
        "    raise NotImplementedError", "", "",
        "@pytest.mark.parametrize(", f'    "{params}",', "    [",
    ]
    for c in cases:
        vals = [repr(c.id)]
        for k in keys:
            v = c.inputs.get(k)
            vals.append("None" if (k not in c.inputs or (isinstance(v, str) and v in skip))
                        else _literal(v))
        vals.append(repr(c.expected))
        lines.append(f"        ({', '.join(vals)}),")
    lines += [
        "    ],", ")", f"def test_{fn}({params}):",
        "    actual = system_under_test(" + ", ".join(f"{i}={i}" for i in idents.values()) + ")",
        '    assert actual == expected, f"{case_id}: expected {expected!r}, got {actual!r}"', "",
    ]
    return "\n".join(lines)
