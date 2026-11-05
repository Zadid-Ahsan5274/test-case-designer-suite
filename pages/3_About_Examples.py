"""Explanations and demo projects."""
import streamlit as st

from core.examples import DECISION_EXAMPLES, FIELD_EXAMPLES
from ui.components import save_button, sidebar_project
from ui.state import init_state, queue_project

st.set_page_config(page_title="About & Examples", page_icon="📘", layout="wide")
init_state()
slot = sidebar_project()

st.title("📘 Examples & how it works")

st.subheader("Load a demo")
c1, c2 = st.columns(2)
with c1:
    st.markdown("**Module A (fields)**")
    for label, fn in FIELD_EXAMPLES.items():
        if st.button(label, key=f"a_{label}"):
            queue_project(fn(), parts=("fields",))
with c2:
    st.markdown("**Module B (decision tables)**")
    for label, fn in DECISION_EXAMPLES.items():
        if st.button(label, key=f"b_{label}"):
            queue_project(fn(), parts=("decision",))

st.subheader("Techniques in one minute")
st.markdown("""
**Boundary Value Analysis (BVA)** - defects cluster at the edges of ranges. For *Age 18-60*:
`17, 18, 19, 59, 60, 61` (3-value mode).

**Equivalence Partitioning (EP)** - inputs that the system should treat the same are one class,
so one representative value per class is enough: valid, below range, above range, wrong type,
empty/null.

**Decision tables** - list every combination of conditions and the expected action.
*Collapsing* merges rules with the same action using `-` (don't care).
*Pairwise* keeps a small set of rows in which every pair of condition values appears together
at least once - most defects are caused by one or two interacting factors.

**Special display tokens:** `<empty>` = empty string, `<null>` = missing value,
`<whitespace xN>` = N spaces.

**Assumptions the tool makes (check them against your requirements):**
whitespace-only text counts as blank, enum matching is case-sensitive, and a string value of
length *n* is generated as `n` times the letter `a`.
""")

save_button(slot)
