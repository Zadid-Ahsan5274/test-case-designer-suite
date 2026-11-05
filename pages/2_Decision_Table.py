"""Module B - Decision Table & Combination Designer."""
import json

import pandas as pd
import streamlit as st

from core.decision_table import (DEFAULT_STEP_TEMPLATE, MAX_ROWS, TooManyCombinations, collapse,
                                 combo_count, combo_key, full_rules, is_equivalent,
                                 pairwise_coverage, pairwise_rules, prune_constraints,
                                 rules_to_testcases, validate, validate_conditions)
from core.examples import DECISION_EXAMPLES
from core.exporters import (rows_module_b, to_csv, to_gherkin, to_json, to_markdown, to_pytest,
                            to_testrail_csv, to_xlsx)
from core.models import DONT_CARE
from core.values import SpecError
from ui.components import download_row, save_button, sidebar_project
from ui.state import (actions_list, df_to_conditions, editor_key, init_state, queue_project,
                      sticky)

st.set_page_config(page_title="Decision Table Designer", page_icon="🔀", layout="wide")
init_state()
slot = sidebar_project()
ss = st.session_state

st.title("🔀 Decision Table & Combination Designer")
st.caption("Define conditions and actions, assign outcomes, then collapse or pairwise-reduce.")

tab1, tab2, tab3 = st.tabs(["1. Define", "2. Assign actions", "3. Results & export"])

# ================================================================= 1. define
with tab1:
    cols = st.columns([1, 1, 3])
    for col, (label, fn) in zip(cols[:2], DECISION_EXAMPLES.items()):
        if col.button(f"Load: {label}", width="stretch"):
            queue_project(fn(), parts=("decision",))

    left, right = st.columns([3, 2])
    with left:
        st.markdown("**Conditions** - one row each, values comma separated (blank = Y, N)")
        ss.cond_live = st.data_editor(
            ss.cond_df, key=editor_key("cond"), num_rows="dynamic", width="stretch",
            column_config={"Condition": st.column_config.TextColumn(required=True),
                           "Values": st.column_config.TextColumn(
                               help="e.g. Y, N   or   Guest, Member, Admin")})
    with right:
        st.markdown("**Actions** - one expected outcome per line")
        sticky(st.text_area, "actions_widget", "", "Actions", height=190,
               label_visibility="collapsed")
        ss.actions_text = ss["actions_widget"]

conds = df_to_conditions(ss.cond_live)
actions = actions_list()
errs = validate_conditions(conds, actions)
if errs:
    for e in errs:
        st.error(e)
    save_button(slot)
    st.stop()

ss.constraints = prune_constraints(conds, ss.constraints)
constraints = ss.constraints

with tab1:
    st.markdown("**Constraints** - combinations that can never happen (excluded from the output)")
    names = [c.name for c in conds]
    k1, k2, k3, k4, k5 = st.columns([2, 1.3, 2, 1.3, 1])
    ca = k1.selectbox("Condition A", names, key="con_a")
    va = k2.selectbox("Value", next(c.values for c in conds if c.name == ca), key="con_va")
    cb = k3.selectbox("cannot occur with B", [n for n in names if n != ca] or names, key="con_b")
    vb = k4.selectbox("Value ", next(c.values for c in conds if c.name == cb), key="con_vb")
    if k5.button("Add", disabled=ca == cb, width="stretch"):
        new = {ca: va, cb: vb}
        if new not in ss.constraints:
            ss.constraints.append(new)
            ss.proj_ver += 1
        st.rerun()
    for i, con in enumerate(list(ss.constraints)):
        r1, r2 = st.columns([8, 1])
        r1.write("🚫 " + "  and  ".join(f"**{k}** = {v}" for k, v in con.items()) + " is impossible")
        if r2.button("Remove", key=f"rm_con_{i}"):
            ss.constraints.pop(i)
            ss.proj_ver += 1
            st.rerun()

# ================================================================= 2. assign actions
full_error = None
try:
    full = full_rules(conds, ss.action_map, constraints, actions)
except TooManyCombinations as e:
    full, full_error = None, str(e)

with tab2:
    if full_error:
        st.warning(full_error)
    view = st.radio("Edit actions on", ["Full table", "Pairwise table"] if full is not None
                    else ["Pairwise table"], horizontal=True, key="grid_view")
    base_rules = full if view == "Full table" else pairwise_rules(conds, ss.action_map,
                                                                  constraints, actions)
    if view == "Pairwise table":
        st.caption("Actions you set here are remembered for the same combinations in the full table.")
    sig = json.dumps([ss.proj_ver, view, [(c.name, c.values) for c in conds], actions, constraints])
    if ss.get("grid_sig") != sig:
        ss.grid_sig = sig
        ss.grid_base = pd.DataFrame(
            [{"Rule": r.id, **r.conditions, **{f"→ {a}": a in r.actions for a in actions}}
             for r in base_rules])
        ss.grid_ver = ss.get("grid_ver", 0) + 1
    st.caption("Tick the expected action(s) for every rule. "
               + (f"{len(base_rules)} rules." if base_rules else ""))
    edited = st.data_editor(
        ss.grid_base, key=f"grid_{ss.grid_ver}", hide_index=True, width="stretch",
        disabled=["Rule", *[c.name for c in conds]],
        column_config={f"→ {a}": st.column_config.CheckboxColumn(a) for a in actions})
    for rule, (_, row) in zip(base_rules, edited.iterrows()):
        ss.action_map[combo_key(conds, rule.conditions)] = [a for a in actions
                                                            if bool(row[f"→ {a}"])]

# recompute with the user's latest ticks
full = None if full_error else full_rules(conds, ss.action_map, constraints, actions)
pw = pairwise_rules(conds, ss.action_map, constraints, actions)
collapsed = collapse(full, conds) if full is not None else None

# ================================================================= 3. results
with tab3:
    f_txt = f"{len(full):,}" if full is not None else f">{MAX_ROWS:,} (not generated)"
    c_txt = str(len(collapsed)) if collapsed is not None else "n/a"
    st.success(f"**Reduction:** Full: {f_txt} rules  →  Collapsed: {c_txt}  →  Pairwise: {len(pw)}")

    if full is not None:
        issues = validate(full, conds, constraints)
        assigned = sum(1 for r in full if r.actions)
        st.progress(assigned / max(len(full), 1),
                    text=f"Actions assigned: {assigned}/{len(full)} rules")
        if not issues:
            st.success("✅ Validation passed: no conflicts, gaps or missing actions.")
        for i in issues:
            {"error": st.error, "warning": st.warning, "info": st.info}[i.level](i.message)
        if collapsed is not None and is_equivalent(full, collapsed, conds):
            st.caption("✅ Merge-safety check: the collapsed table gives exactly the same "
                       "outcome as the full table for every combination.")

    covered, total = pairwise_coverage(conds, pw, constraints)
    st.caption(f"Pairwise coverage: {covered}/{total} value pairs covered "
               f"({100 * covered // max(total, 1)}%). Full table has "
               f"{combo_count(conds):,} raw combinations.")

    options = (["Full", "Collapsed"] if full is not None else []) + ["Pairwise"]
    mode = st.radio("Generate test cases from", options, horizontal=True, index=len(options) - 1
                    if full is None else 1, key="out_mode")
    rules = {"Full": full, "Collapsed": collapsed, "Pairwise": pw}[mode]

    with st.expander("Step wording"):
        tpl = st.text_input("Step template", DEFAULT_STEP_TEMPLATE,
                            help="Use {condition} and {value}")
        final = st.text_input("Final step", "Execute the scenario and observe the result")
    try:
        cases = rules_to_testcases(rules, f"Decision table ({mode.lower()})",
                                   ss.get("prefix", "TC"), tpl, final)
    except SpecError as e:
        st.error(str(e))
        save_button(slot)
        st.stop()

    st.markdown(f"**Rules table ({mode.lower()})** - `{DONT_CARE}` means don't care")
    st.dataframe(pd.DataFrame([{"Rule": r.id, **r.conditions,
                                "Action(s)": " + ".join(r.actions) or "(none)"} for r in rules]),
                 width="stretch", hide_index=True)
    st.markdown(f"**Test cases ({len(cases)})**")
    rows = rows_module_b(cases)
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    slug = "".join(ch if ch.isalnum() else "_" for ch in ss.get("project_name", "tests")) or "tests"
    download_row([
        ("CSV", to_csv(rows), f"{slug}_decision.csv", "text/csv"),
        ("Excel", to_xlsx({"Test cases": rows, "Rules": [
            {"Rule": r.id, **r.conditions, "Action(s)": " + ".join(r.actions)} for r in rules]}),
         f"{slug}_decision.xlsx",
         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("JSON", to_json(rows), f"{slug}_decision.json", "application/json"),
        ("Markdown", to_markdown(rows), f"{slug}_decision.md", "text/markdown"),
    ])
    download_row([
        ("Gherkin", to_gherkin(cases, ss.get("project_name", "Decision table"), [DONT_CARE]),
         f"{slug}.feature", "text/plain"),
        ("pytest skeleton", to_pytest(cases, slug, [DONT_CARE]), f"test_{slug.lower()}.py",
         "text/x-python"),
        ("TestRail / Zephyr CSV", to_testrail_csv(cases, "Decision table"),
         f"{slug}_testrail.csv", "text/csv"),
    ])

save_button(slot)
