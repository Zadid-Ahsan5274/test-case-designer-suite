"""Reusable Streamlit components."""
from __future__ import annotations

import streamlit as st

from core.project import ProjectError, project_from_json, project_to_json
from .state import current_project, queue_project, sticky


def sidebar_project():
    """Render the project sidebar. Returns a slot for the Save button, which must be filled
    with `save_button(slot)` AFTER the page has processed its editors (so the saved file is
    never one edit behind)."""
    ss = st.session_state
    with st.sidebar:
        st.header("Project")
        sticky(st.text_input, "project_name", "My project", "Project name")
        sticky(st.text_input, "prefix", "TC", "Test case ID prefix",
               help="IDs look like PREFIX-001, e.g. TC-LOGIN-001")
        slot = st.container()
        up = st.file_uploader("Load project (.json)", type=["json"], key="project_upload")
        if up is not None:
            sig = f"{up.name}:{up.size}"
            if ss.get("_loaded_sig") != sig:
                ss["_loaded_sig"] = sig
                try:
                    queue_project(project_from_json(up.getvalue()))
                except ProjectError as e:
                    st.error(str(e))
        st.caption("All processing happens in your session. Nothing is stored on a server.")
    return slot


def save_button(slot) -> None:
    proj = current_project()
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in proj.name) or "project"
    with slot:
        st.download_button("Save project (.json)", project_to_json(proj),
                           file_name=f"{safe}.json", mime="application/json", width="stretch",
                           help="Hosted apps keep nothing between sessions - save your work here.")


def download_row(buttons: list[tuple[str, object, str, str]]) -> None:
    """buttons: (label, data, filename, mime)"""
    cols = st.columns(len(buttons))
    for col, (label, data, name, mime) in zip(cols, buttons):
        col.download_button(label, data, file_name=name, mime=mime, width="stretch")


def result_icon(expected: str) -> str:
    if expected == "Accept":
        return f"✅ {expected}"
    if expected.lower().startswith("reject"):
        return f"❌ {expected}"
    return expected
