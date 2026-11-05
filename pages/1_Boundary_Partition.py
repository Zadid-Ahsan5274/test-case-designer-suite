"""Module A - Boundary & Partition Designer."""
import pandas as pd
import streamlit as st

from core.bva import MODE_HELP, MODES
from core.combiner import STRATEGIES, build_testcases
from core.examples import FIELD_EXAMPLES
from core.exporters import (rows_module_a, to_csv, to_gherkin, to_json, to_markdown,
                            to_pytest, to_testrail_csv, to_xlsx)
from core.models import FIELD_TYPES, TYPE_HELP, Condition
from core.partitions import ep_classes
from core.project import Project
from core.values import SpecError, display
from ui.components import download_row, result_icon, save_button, sidebar_project
from ui.state import (actions_list, df_to_fields, editor_key, init_state, queue_project,
                      sticky)

st.set_page_config(page_title="Boundary & Partition Designer", page_icon="🎯", layout="wide")
init_state()
slot = sidebar_project()
ss = st.session_state

st.title("🎯 Boundary & Partition Designer")
st.caption("Boundary Value Analysis (BVA) + Equivalence Partitioning (EP) for one or many fields.")

# ---------------------------------------------------------------- 1. define fields
st.subheader("1. Define your fields")
cols = st.columns([1, 1, 3])
for col, (label, fn) in zip(cols[:2], FIELD_EXAMPLES.items()):
    if col.button(f"Load: {label}", width="stretch"):
        queue_project(fn(), parts=("fields",))

with st.expander("How to fill the table"):
    st.markdown("\n".join(f"- **{t}**: {h}" for t, h in TYPE_HELP.items()))

key = editor_key("fields")
ss.fields_live = st.data_editor(
    ss.fields_df, key=key, num_rows="dynamic", width="stretch",
    column_config={
        "Name": st.column_config.TextColumn(required=True),
        "Type": st.column_config.SelectboxColumn(options=list(FIELD_TYPES), required=True,
                                                 default="int"),
        "Min": st.column_config.TextColumn(help="Min value / min length / min date"),
        "Max": st.column_config.TextColumn(help="Max value / max length / max date"),
        "Step": st.column_config.TextColumn(help="Optional. int: 1, decimal: 0.01, date: days"),
        "Allowed values": st.column_config.TextColumn(help="Enum only, comma separated"),
        "Required": st.column_config.CheckboxColumn(default=True),
        "On invalid": st.column_config.TextColumn(
            default="Reject with error", help="Expected result text for invalid input"),
    })

# ---------------------------------------------------------------- 2. settings
st.subheader("2. Choose how to generate")
c1, c2 = st.columns(2)
with c1:
    mode = sticky(st.selectbox, "bva_mode", "3-value", "Boundary mode", MODES,
                  format_func=lambda m: f"{m}: {MODE_HELP[m]}")
with c2:
    strategy = sticky(st.selectbox, "strategy", "vary_one", "Combination strategy",
                      list(STRATEGIES), format_func=lambda k: STRATEGIES[k])

specs = df_to_fields(ss.fields_live)
try:
    gen = build_testcases(specs, mode, strategy, ss.get("prefix", "TC"))
except SpecError as e:
    st.error("Please fix the field table first:\n\n" + str(e))
    save_button(slot)
    st.stop()

# ---------------------------------------------------------------- 3. results
st.subheader("3. Test cases")
accept = sum(1 for c in gen.cases if c.expected == "Accept")
m1, m2, m3 = st.columns(3)
m1.metric("Test cases", len(gen.cases))
m2.metric("Expected to be accepted", accept)
m3.metric("Expected to be rejected", len(gen.cases) - accept)
for n in gen.notes:
    st.info(n)

tab_all, tab_field = st.tabs(["All test cases", "Values per field"])
with tab_all:
    df = pd.DataFrame(rows_module_a(gen.cases, max_len=40))
    df["Expected Result"] = df["Expected Result"].map(result_icon)
    st.dataframe(df, width="stretch", hide_index=True)
with tab_field:
    for fname, cs in gen.field_cases.items():
        with st.expander(f"{fname}  ({len(cs)} values)", expanded=len(gen.field_cases) == 1):
            st.dataframe(pd.DataFrame([{
                "Value": display(c.value, 40), "Technique": c.technique,
                "Partition": c.partition, "Valid?": "✅ valid" if c.valid else "❌ invalid",
                "Rationale": c.rationale} for c in cs]), width="stretch", hide_index=True)

# ---------------------------------------------------------------- 4. export
st.subheader("4. Export")
rows = rows_module_a(gen.cases)
slug = "".join(ch if ch.isalnum() else "_" for ch in ss.get("project_name", "tests")) or "tests"
download_row([
    ("CSV", to_csv(rows), f"{slug}_boundary.csv", "text/csv"),
    ("Excel", to_xlsx({"Test cases": rows,
                       "Values per field": [{"Field": f, "Value": display(c.value),
                                             "Technique": c.technique, "Partition": c.partition,
                                             "Valid": c.valid, "Rationale": c.rationale}
                                            for f, cs in gen.field_cases.items() for c in cs]}),
     f"{slug}_boundary.xlsx",
     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ("JSON", to_json(rows), f"{slug}_boundary.json", "application/json"),
    ("Markdown", to_markdown(rows), f"{slug}_boundary.md", "text/markdown"),
])
download_row([
    ("Gherkin", to_gherkin(gen.cases, ss.get("project_name", "Generated")),
     f"{slug}.feature", "text/plain"),
    ("pytest skeleton", to_pytest(gen.cases, slug), f"test_{slug.lower()}.py", "text/x-python"),
    ("TestRail / Zephyr CSV", to_testrail_csv(gen.cases, "Boundary & Partition"),
     f"{slug}_testrail.csv", "text/csv"),
])

# ---------------------------------------------------------------- 5. hand over to module B
with st.expander("Use these partitions in the Decision Table designer"):
    st.write("Turn field partitions (Valid / Below range / Above range / ...) into decision-table "
             "conditions. This replaces the conditions, rules and constraints of Module B.")
    chosen = st.multiselect("Fields", [s.name for s in specs], default=[s.name for s in specs][:3])
    if st.button("Send to Decision Table", disabled=not chosen):
        conds = [Condition(s.name, ep_classes(s)) for s in specs if s.name in chosen]
        queue_project(Project(conditions=conds, actions=actions_list() or ["Accept", "Reject"]),
                      parts=("decision",))

save_button(slot)
