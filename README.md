# Test Case Designer

Deterministic test-case design for QA engineers - **no AI, no database, same input = same output.**

| Module | What it does |
|---|---|
| **A. Boundary & Partition Designer** | Boundary Value Analysis (2-value, 3-value, robust) + Equivalence Partitioning for int, decimal, text length, date, enum and boolean fields. Combines fields by *one-field-at-a-time*, *pairwise on valid values*, or per-field. Every case has a rationale. |
| **B. Decision Table & Combination Designer** | Conditions + actions -> full table, **collapsed** table (don't-care merging, proven equivalent), and **pairwise** table. Constraints, conflict/gap/incomplete validation, reduction banner, coverage summary, test-case generation. |

Exports: CSV, Excel, JSON, Markdown, Gherkin, pytest skeleton, TestRail/Zephyr-style CSV.
Projects are saved/loaded as `.json` (hosted apps are stateless).

## Run locally
```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
streamlit run app.py
pytest -q
```

## Publish for free (no domain needed)
1. Push this folder to a **public GitHub repo** (`app.py` at the repo root).
2. Go to <https://share.streamlit.io>, sign in with GitHub, click **Create app**, pick the repo, branch `main`, main file `app.py`.
3. Deploy. You get `https://<name>.streamlit.app`. Add that link to this README.

## Project layout
```
app.py                  home page
pages/                  Streamlit pages (Module A, Module B, About)
core/                   pure Python logic - no Streamlit imports
  values.py bva.py partitions.py combiner.py pairwise.py
  decision_table.py exporters.py project.py examples.py models.py
ui/                     session-state + shared widgets
tests/                  pytest + Hypothesis + Streamlit AppTest smoke tests
examples/               sample project files (use "Load project" in the sidebar)
```

## How the rules work
* **3-value BVA** for `Age 18-60`: `17, 18, 19, 59, 60, 61`. **Robust** adds a nominal value and extremes (0, -1, INT_MAX, leap day, ...).
* **Collapse** merges two rules only if their actions are identical and they differ in one condition whose values are all present - so no behaviour is ever lost (verified by property tests).
* **Pairwise** uses a built-in deterministic greedy algorithm (no dependency).
* Display tokens: `<empty>`, `<null>`, `<whitespace xN>`. A text value of length *n* is `n` x `a`.
* Assumptions (verify against your requirements): whitespace-only text = blank; enum matching is case-sensitive.

## Ideas for next versions
Regex/format rules for strings, Module A -> B import of custom partitions, state-transition tables, OpenAPI import.
