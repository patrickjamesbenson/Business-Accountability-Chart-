# app.py — Success Dynamics Accountability Chart (Streamlit)
# -----------------------------------------------------------
# Adds Revenue Streams breakdown that rolls up to a 12‑month goal.
# Single-file Streamlit app:
# - Capture revenue streams (name + target value + notes), with option to sync sum to goal
# - Define core functions (Sales & Marketing, Operations, Finance) + custom ones
# - Add roles per function, assign people, specify ReportsTo
# - Record KPIs and Accountabilities per role
# - Visualise structure as a tree (Graphviz)
# - Import/Export JSON and CSV
#
# Usage:
#   pip install -r requirements.txt
#   streamlit run app.py
#
# CSV import expects columns: Function,Role,Person,FTE,ReportsTo,KPIs,Accountabilities,Notes
# JSON import/export uses the app's internal format (business, functions, roles, revenue_streams).
#
from __future__ import annotations

import json
from io import StringIO
from typing import Dict, List, Any

import pandas as pd
import streamlit as st

# ---------- Helpers ----------
CORE_FUNCTIONS = ["Sales & Marketing", "Operations", "Finance"]
ROLE_COLUMNS = [
    "Function",        # e.g., Sales & Marketing / Operations / Finance / Custom
    "Role",            # e.g., Sales Manager
    "Person",          # e.g., Alex Smith (one person per role)
    "FTE",             # 0.0–1.0
    "ReportsTo",       # Role name this role reports to (optional)
    "KPIs",            # Comma-separated KPI names
    "Accountabilities",# Free text, bullet list lines
    "Notes"            # Free text
]

REVENUE_COLUMNS = ["Stream", "TargetValue", "Notes"]

DEFAULT_ROWS = [
    {"Function": f, "Role": "", "Person": "", "FTE": 1.0, "ReportsTo": "", "KPIs": "", "Accountabilities": "", "Notes": ""}
    for f in CORE_FUNCTIONS
]

DEFAULT_STREAMS = [
    {"Stream": "New Clients", "TargetValue": 400000, "Notes": ""},
    {"Stream": "Subscriptions / Recurring", "TargetValue": 300000, "Notes": ""},
    {"Stream": "Upsell (New Program)", "TargetValue": 250000, "Notes": ""},
    {"Stream": "Other / Experiments", "TargetValue": 50000, "Notes": ""},
]

@st.cache_data(show_spinner=False)
def empty_df() -> pd.DataFrame:
    return pd.DataFrame(DEFAULT_ROWS, columns=ROLE_COLUMNS)

@st.cache_data(show_spinner=False)
def empty_streams_df() -> pd.DataFrame:
    return pd.DataFrame(DEFAULT_STREAMS, columns=REVENUE_COLUMNS)

@st.cache_data(show_spinner=False)
def csv_template() -> str:
    df = empty_df()
    return df.to_csv(index=False)

@st.cache_data(show_spinner=False)
def example_json() -> Dict[str, Any]:
    return {
        "business": {
            "name": "My Business",
            "revenue_goal": 1_000_000
        },
        "functions": CORE_FUNCTIONS,
        "roles": [
            {"Function": "Sales & Marketing", "Role": "Head of Sales", "Person": "Jordan Pike", "FTE": 1.0, "ReportsTo": "", "KPIs": "Revenue,Win Rate", "Accountabilities": "Own sales plan; forecast; pipeline reviews", "Notes": "Priority hire"},
            {"Function": "Operations", "Role": "Production Lead", "Person": "Sam Lee", "FTE": 1.0, "ReportsTo": "", "KPIs": "OTIF,COGS%", "Accountabilities": "Schedule; QA; supplier mgmt", "Notes": ""},
            {"Function": "Finance", "Role": "Bookkeeper", "Person": "Morgan Tan", "FTE": 0.6, "ReportsTo": "", "KPIs": "Debtor days,Cash runway", "Accountabilities": "AP/AR; payroll prep; BAS packs", "Notes": ""},
            {"Function": "Sales & Marketing", "Role": "BDM", "Person": "Jordan Pike", "FTE": 1.0, "ReportsTo": "Head of Sales", "KPIs": "New logos,Meetings/week", "Accountabilities": "Prospecting; demos; proposals", "Notes": "Same person as Head of Sales for now"}
        ],
        "revenue_streams": DEFAULT_STREAMS
    }

# Simple, readable DOT label — escapes quotes and newlines
def _esc(s: str) -> str:
    return (s or "").replace("\n", "\\n").replace('"', '\"')

def build_graphviz_dot(business_name: str, revenue_goal: float, df: pd.DataFrame) -> str:
    """Create a Graphviz DOT for the accountability chart.
    - Functions are clusters
    - Roles are nodes. Node label shows Role and Person.
    - Optional edges from ReportsTo -> Role (intra- or cross-function allowed)
    """
    business_label = f"{business_name}\n12‑month Goal: ${revenue_goal:,.0f}"

    roles = df["Role"].fillna("").astype(str).str.strip()
    people = df["Person"].fillna("").astype(str).str.strip()
    funcs  = df["Function"].fillna("").astype(str).str.strip()

    duplicates = roles[roles != ""].duplicated(keep=False)
    duplicate_names = sorted(set(roles[duplicates]))

    grouped = df.assign(Role=roles, Person=people, Function=funcs).groupby("Function")

    dot = [
        "digraph G {",
        "  graph [rankdir=TB, splines=ortho];",
        '  node  [shape=box, style=rounded, fontname=Helvetica];',
        "  edge  [arrowhead=vee];",
        f'  root [label="{_esc(business_label)}", shape=box, style="rounded,bold"];',
    ]

    for func, gdf in grouped:
        f_id = f"cluster_{abs(hash(func)) % (10**8)}"
        dot.append(f"  subgraph {f_id} {{")
        dot.append('    color=lightgray; style=rounded;')
        dot.append('    labeljust="l"; labelloc="t";')
        dot.append('    fontsize=12;')
        dot.append('    fontname="Helvetica";')
        dot.append('    pencolor="lightgray";')
        dot.append('    label="' + _esc(func) + '";')
        func_node_id = f"func_{abs(hash(func)) % (10**8)}"
        dot.append(f'    {func_node_id} [label="{_esc(func)}", shape=box, style="rounded,filled", fillcolor="#f5f5f5"];')
        dot.append(f"    root -> {func_node_id};")
        for _, row in gdf.iterrows():
            role = row.get("Role", "").strip()
            person = row.get("Person", "").strip()
            if not role:
                continue
            node_id = f"role_{abs(hash(role)) % (10**10)}"
            label = role if not person else f"{role}\n({person})"
            dot.append(f'    {node_id} [label="{_esc(label)}"];')
            dot.append(f"    {func_node_id} -> {node_id};")
        dot.append("  }")

    for _, row in df.iterrows():
        role = (row.get("Role", "") or "").strip()
        mgr  = (row.get("ReportsTo", "") or "").strip()
        if role and mgr:
            src = f"role_{abs(hash(mgr)) % (10**10)}"
            dst = f"role_{abs(hash(role)) % (10**10)}"
            dot.append(f"  {src} -> {dst};")

    if duplicate_names:
        warn = "Duplicate role names: " + ", ".join(duplicate_names)
        dot.append(f'  warning [label="{_esc(warn)}", shape=note, color=red, fontcolor=red];')

    dot.append("}")
    return "\n".join(dot)


# ---------- UI ----------
st.set_page_config(page_title="Success Dynamics – Accountability Chart", layout="wide", initial_sidebar_state="expanded")

# Sidebar — Branding & Business
with st.sidebar:
    st.markdown("### Branding")
    logo = st.file_uploader("Upload Success Dynamics logo (PNG/JPG/SVG)", type=["png", "jpg", "jpeg", "svg"])
    if logo:
        st.image(logo, use_container_width=True)
    else:
        st.markdown("**Success Dynamics**")

    st.markdown("---")
    st.markdown("### Business Setup")
    business_name = st.text_input("Business name", value="My Business")

    st.markdown("### Revenue Goal & Streams")
    if "revenue_streams_df" not in st.session_state:
        st.session_state.revenue_streams_df = empty_streams_df()

    # Toggle: lock business revenue goal to sum of streams
    lock_goal = st.checkbox("Lock revenue goal to sum of streams", value=True, help="When enabled, the goal equals the total of the revenue streams below.")

# Main — Revenue Streams then Roles
st.title("Accountability Chart Builder")

# Revenue Streams Editor
st.subheader("Revenue Streams (12‑month)")
rev_df = st.session_state.revenue_streams_df
# Ensure columns
for c in REVENUE_COLUMNS:
    if c not in rev_df.columns:
        rev_df[c] = ""

rev_df["Stream"] = rev_df["Stream"].astype(str)
rev_df["TargetValue"] = pd.to_numeric(rev_df["TargetValue"], errors="coerce").fillna(0.0).clip(0.0)
rev_df["Notes"] = rev_df["Notes"].astype(str)

rev_editor = st.data_editor(
    rev_df,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Stream": st.column_config.TextColumn(required=True),
        "TargetValue": st.column_config.NumberColumn(min_value=0.0, step=1000.0, format="%0.0f"),
        "Notes": st.column_config.TextColumn(),
    },
    hide_index=True,
    key="revenue_editor",
)
st.session_state.revenue_streams_df = rev_editor

streams_total = float(rev_editor["TargetValue"].sum())
st.metric("Total of Streams", f"${streams_total:,.0f}")

# Revenue goal field: locked or free
if lock_goal:
    revenue_goal = streams_total
    st.caption("Revenue goal is locked to the sum of streams above.")
else:
    revenue_goal = st.number_input("12‑month revenue goal ($)", min_value=0.0, value=max(1_000_000.0, streams_total), step=50_000.0, format="%0.0f")

st.markdown("---")

# Functions & Data Import/Export
col_left, col_right = st.columns([2,1])
with col_left:
    st.subheader("Functions")
    if "functions" not in st.session_state:
        st.session_state.functions = CORE_FUNCTIONS.copy()

    custom_func = st.text_input("Add a function")
    add_f, reset_f = st.columns(2)
    with add_f:
        if st.button("➕ Add Function") and custom_func.strip():
            if custom_func not in st.session_state.functions:
                st.session_state.functions.append(custom_func.strip())
    with reset_f:
        if st.button("Reset to Core Functions"):
            st.session_state.functions = CORE_FUNCTIONS.copy()

    st.caption("Current functions: " + ", ".join(st.session_state.functions))

with col_right:
    st.subheader("Import / Export")
    uploaded_csv = st.file_uploader("Import Roles CSV", type=["csv"], key="csv")
    uploaded_json = st.file_uploader("Import JSON (full app data)", type=["json"], key="json")

if "roles_df" not in st.session_state:
    st.session_state.roles_df = empty_df()

# Handle imports
if uploaded_csv is not None:
    try:
        df_in = pd.read_csv(uploaded_csv)
        missing = [c for c in ROLE_COLUMNS if c not in df_in.columns]
        if missing:
            st.error(f"CSV missing columns: {missing}")
        else:
            st.session_state.roles_df = df_in[ROLE_COLUMNS].copy()
            st.success("CSV imported.")
    except Exception as e:
        st.error(f"CSV import failed: {e}")

if uploaded_json is not None:
    try:
        data = json.load(uploaded_json)
        st.session_state.functions = data.get("functions", CORE_FUNCTIONS).copy()
        b = data.get("business", {})
        if b:
            business_name = b.get("name", business_name)
        roles = data.get("roles", [])
        revs = data.get("revenue_streams", DEFAULT_STREAMS)
        st.session_state.revenue_streams_df = pd.DataFrame(revs, columns=REVENUE_COLUMNS)
        df_in = pd.DataFrame(roles)
        missing = [c for c in ROLE_COLUMNS if c not in df_in.columns]
        if missing:
            st.error(f"JSON roles missing columns: {missing}")
        else:
            st.session_state.roles_df = df_in[ROLE_COLUMNS].copy()
            st.success("JSON imported.")
    except Exception as e:
        st.error(f"JSON import failed: {e}")

st.subheader("Roles & Assignments")
funcs_opts = st.session_state.functions
df = st.session_state.roles_df

for col in ROLE_COLUMNS:
    if col not in df.columns:
        df[col] = ""

df["Function"] = df["Function"].astype(str)
df["Role"] = df["Role"].astype(str)
df["Person"] = df["Person"].astype(str)
df["FTE"] = pd.to_numeric(df["FTE"], errors="coerce").fillna(1.0).clip(0.0, 1.0)
df["ReportsTo"] = df["ReportsTo"].astype(str)

edited = st.data_editor(
    df,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Function": st.column_config.SelectboxColumn(options=funcs_opts, required=True),
        "FTE": st.column_config.NumberColumn(min_value=0.0, max_value=1.0, step=0.1, format="%0.1f"),
        "KPIs": st.column_config.TextColumn(help="Comma‑separated list"),
        "Accountabilities": st.column_config.TextColumn(help="Bullets or lines"),
    },
    hide_index=True,
    key="roles_editor",
)
st.session_state.roles_df = edited

tip = "‘ReportsTo’ should reference another *Role* name (not a person). Leave blank to attach directly under the Function header."
st.markdown(f":blue[Tip:] {tip}")

colA, colB, colC = st.columns(3)
with colA:
    if st.button("Add Blank Role Row"):
        st.session_state.roles_df.loc[len(st.session_state.roles_df)] = {c: "" for c in ROLE_COLUMNS}
        st.session_state.roles_df.at[len(st.session_state.roles_df)-1, "FTE"] = 1.0
with colB:
    if st.button("Load Example Data"):
        eg = example_json()
        st.session_state.functions = eg["functions"].copy()
        st.session_state.roles_df = pd.DataFrame(eg["roles"], columns=ROLE_COLUMNS)
        st.session_state.revenue_streams_df = pd.DataFrame(eg["revenue_streams"], columns=REVENUE_COLUMNS)
        st.success("Loaded example.")
with colC:
    export_data = {
        "business": {"name": business_name, "revenue_goal": revenue_goal},
        "functions": st.session_state.functions,
        "roles": st.session_state.roles_df.fillna("").to_dict(orient="records"),
        "revenue_streams": st.session_state.revenue_streams_df.fillna("").to_dict(orient="records"),
    }
    st.download_button("Export JSON", data=json.dumps(export_data, indent=2), file_name="accountability_chart.json", mime="application/json")

csv_buf = StringIO()
st.session_state.roles_df.to_csv(csv_buf, index=False)
st.download_button("Export Roles CSV", data=csv_buf.getvalue(), file_name="accountability_chart_roles.csv", mime="text/csv")

st.download_button("Download Roles CSV Template", data=csv_template(), file_name="accountability_chart_template.csv", mime="text/csv")

st.markdown("---")

# Validation + Graph
st.subheader("Structure & Visualisation")
roles_ser = st.session_state.roles_df["Role"].fillna("").astype(str).str.strip()
if (roles_ser != "").sum() == 0:
    st.info("Add at least one Role to render the chart.")
else:
    dot = build_graphviz_dot(business_name, float(revenue_goal), st.session_state.roles_df)
    st.graphviz_chart(dot, use_container_width=True)

    dups = roles_ser[roles_ser != ""].duplicated(keep=False)
    dup_names = sorted(set(roles_ser[dups]))
    if dup_names:
        st.warning("Duplicate role names detected: " + ", ".join(dup_names) + ". Rename roles so each is unique.")

    rt = st.session_state.roles_df["ReportsTo"].fillna("").astype(str).str.strip()
    bad_refs = sorted(set(rt[(rt != "") & (~rt.isin(roles_ser))]))
    if bad_refs:
        st.warning("ReportsTo references missing: " + ", ".join(bad_refs) + ". Ensure each ‘ReportsTo’ matches an existing Role name.")

st.markdown("---")

with st.expander("How this aligns to the Accountability Chart process"):
    st.markdown(
        """
        **Step 1 – List your current staff** → Use the *Person* column and optionally leave *Role* blank to start.

        **Step 2 – Set your 12‑month revenue goal** → Drive this from **Revenue Streams** (lock toggle) or set a free goal.

        **Step 3 – Define the roles needed** → Add rows under the appropriate *Function* and fill in *Role*. Avoid shaping roles to current staff.

        **Step 4 – Confirm your major functions** → Start with Sales & Marketing, Operations, Finance. Add others as needed.

        **Step 5 – Add roles to each function** → In the table.

        **Step 6 – Add people** → Fill the *Person* column. One person per role row. A person may appear in multiple roles as needed.

        Then use *ReportsTo* to map reporting lines, and visualise the result above.
        """
    )

st.caption("© 2025 • Success Dynamics Accountability Chart • Streamlit app")
