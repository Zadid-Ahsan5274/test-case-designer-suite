"""Session-state helpers: DataFrame <-> dataclass conversion, project load/save, sticky widgets."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core.examples import default_project
from core.models import FIELD_TYPES, Condition, FieldSpec
from core.project import Project
from core.values import is_blank

FIELD_COLUMNS = ["Name", "Type", "Min", "Max", "Step", "Allowed values", "Required", "On invalid"]
COND_COLUMNS = ["Condition", "Values"]


def _s(x) -> str:
    return "" if is_blank(x) else str(x).strip()


# ------------------------------------------------------------ DataFrame <-> dataclasses
def fields_to_df(fields: list[FieldSpec]) -> pd.DataFrame:
    rows = [[f.name, f.type, "" if f.min is None else str(f.min), "" if f.max is None else str(f.max),
             "" if f.step is None else str(f.step), ", ".join(f.allowed), bool(f.required),
             f.on_invalid] for f in fields]
    return pd.DataFrame(rows, columns=FIELD_COLUMNS)


def df_to_fields(df: pd.DataFrame) -> list[FieldSpec]:
    out = []
    for rec in df.to_dict("records"):
        name, mn, mx = _s(rec.get("Name")), _s(rec.get("Min")), _s(rec.get("Max"))
        allowed = [a.strip() for a in _s(rec.get("Allowed values")).split(",") if a.strip()]
        if not (name or mn or mx or allowed):
            continue  # blank row
        req = rec.get("Required")
        required = True if is_blank(req) else bool(req)
        typ = _s(rec.get("Type")) or "int"
        out.append(FieldSpec(
            name=name, type=typ if typ in FIELD_TYPES else "int", min=mn or None, max=mx or None,
            step=_s(rec.get("Step")) or None, allowed=allowed, required=required,
            on_invalid=_s(rec.get("On invalid")) or "Reject with error"))
    return out


def conditions_to_df(conds: list[Condition]) -> pd.DataFrame:
    return pd.DataFrame([[c.name, ", ".join(c.values)] for c in conds], columns=COND_COLUMNS)


def df_to_conditions(df: pd.DataFrame) -> list[Condition]:
    out = []
    for rec in df.to_dict("records"):
        name, vals = _s(rec.get("Condition")), _s(rec.get("Values"))
        if not name and not vals:
            continue
        values = [v.strip() for v in vals.split(",") if v.strip()] or ["Y", "N"]
        out.append(Condition(name, values))
    return out


def actions_list() -> list[str]:
    return [a.strip() for a in st.session_state.actions_text.splitlines() if a.strip()]


# ------------------------------------------------------------ project <-> session
def _apply(p: Project, parts) -> None:
    ss = st.session_state
    everything = parts is None
    forget: list[str] = []  # widget keys to re-seed from their _keep_* copies
    if everything:
        ss["_keep_project_name"], ss["_keep_prefix"] = p.name, p.prefix
        forget += ["project_name", "prefix"]
    if everything or "fields" in parts:
        df = fields_to_df(p.fields)
        ss.fields_df, ss.fields_live = df, df
        ss.fields_ver = ss.get("fields_ver", 0) + 1
        ss["_keep_bva_mode"], ss["_keep_strategy"] = p.bva_mode, p.strategy
        forget += ["bva_mode", "strategy"]
    if everything or "decision" in parts:
        df = conditions_to_df(p.conditions)
        ss.cond_df, ss.cond_live = df, df
        ss.cond_ver = ss.get("cond_ver", 0) + 1
        ss.actions_text = "\n".join(p.actions)
        ss["_keep_actions_widget"] = ss.actions_text
        forget.append("actions_widget")
        ss.action_map = dict(p.action_map)
        ss.constraints = [dict(c) for c in p.constraints]
        ss.proj_ver = ss.get("proj_ver", 0) + 1
    for k in forget:
        ss.pop(k, None)


def queue_project(p: Project, parts=None) -> None:
    """Load a project on the next run (before any widget exists), then rerun."""
    st.session_state["_pending"] = (p, parts)
    st.rerun()


def init_state() -> None:
    ss = st.session_state
    pending = ss.pop("_pending", None)
    if "fields_df" not in ss:
        _apply(default_project(), None)
        ss.setdefault("fields_ver", 1)
    if pending:
        _apply(*pending)


def current_project() -> Project:
    ss = st.session_state
    return Project(
        name=ss.get("project_name", "My project"), prefix=ss.get("prefix", "TC"),
        bva_mode=ss.get("bva_mode", "3-value"), strategy=ss.get("strategy", "vary_one"),
        fields=df_to_fields(ss.fields_live), conditions=df_to_conditions(ss.cond_live),
        actions=actions_list(), action_map=dict(ss.action_map),
        constraints=[dict(c) for c in ss.constraints])


# ------------------------------------------------------------ widgets that survive page changes
def sticky(widget, key: str, default, *args, **kwargs):
    """Streamlit drops widget state when its page is not shown. Keep a copy and re-seed."""
    ss = st.session_state
    if key not in ss:
        ss[key] = ss.get(f"_keep_{key}", default)
    val = widget(*args, key=key, **kwargs)
    ss[f"_keep_{key}"] = val
    return val


def editor_key(name: str) -> str:
    """Key for a dynamic data_editor. If its widget state was lost (page switch) the last
    edited table becomes the new base so no edits disappear."""
    ss = st.session_state
    key = f"{name}_editor_{ss[name + '_ver']}"
    if key not in ss:
        ss[f"{name}_df"] = ss[f"{name}_live"]
    return key
