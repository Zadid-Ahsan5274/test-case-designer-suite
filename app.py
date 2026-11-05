"""Test Case Designer - home page."""
import streamlit as st

from ui.components import save_button, sidebar_project
from ui.state import init_state

st.set_page_config(page_title="Test Case Designer", page_icon="🧪", layout="wide")
init_state()
slot = sidebar_project()

st.title("🧪 Test Case Designer")
st.write("Turn requirements into test cases in minutes using classic, deterministic techniques. "
         "No AI guessing: the same input always gives the same output.")

c1, c2 = st.columns(2)
with c1:
    st.subheader("🎯 Boundary & Partition Designer")
    st.write("Define fields (integer, decimal, text length, date, list, boolean) and get "
             "**Boundary Value Analysis** and **Equivalence Partitioning** cases, combined "
             "across fields, with a rationale for every case.")
    st.page_link("pages/1_Boundary_Partition.py", label="Open Module A", icon="🎯")
with c2:
    st.subheader("🔀 Decision Table & Combination Designer")
    st.write("Define conditions and actions, assign outcomes, then view the **full**, "
             "**collapsed** or **pairwise** table with validation, plus ready test cases.")
    st.page_link("pages/2_Decision_Table.py", label="Open Module B", icon="🔀")

st.divider()
st.markdown("""
**Export to:** CSV, Excel, JSON, Markdown, Gherkin, pytest skeleton, TestRail/Zephyr-style CSV.  
**Tip:** this app is hosted, so it does not remember your work. Use **Save project** in the sidebar.
""")
st.page_link("pages/3_About_Examples.py", label="Examples & how it works", icon="📘")

save_button(slot)
