# app.py — Success Dynamics Accountability Chart (Streamlit) — v4
# ----------------------------------------------------------------
# New in v4 (on top of v3):
# • Tracking feature (monthly): plan vs actuals, cost-of-sales, per-person fixed costs, other overheads
# • Sidebar quick-entry for a chosen month; main panel editors and charts
# • YTD metrics + annualised run-rate projection vs goal
#
from __future__ import annotations

import json, os, re, shutil, calendar
from io import StringIO
from typing import Dict, List, Any

import pandas as pd
import streamlit as st

# ---------- Constants & Helpers ----------
CORE_FUNCTIONS = ["Sales & Marketing", "Operations", "Finance"]
ROLE_COLUMNS = ["Function","Role","Person","FTE","ReportsTo","KPIs","Accountabilities","Notes"]
REVENUE_COLUMNS = ["Stream","TargetValue","Notes"]
MONTHS = list(calendar.month_name)[1:]  # ["January", ..., "December"]

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
PROFILES_DIR = os.path.join(APP_ROOT, "data", "profiles")
LOGOS_DIR    = os.path.join(APP_ROOT, "data", "logos")
os.makedirs(PROFILES_DIR, exist_ok=True)
os.makedirs(LOGOS_DIR, exist_ok=True)

# Ensure .gitkeep exists for GitHub web uploads
for d in (PROFILES_DIR, LOGOS_DIR):
    keep = os.path.join(d, ".gitkeep")
    if not os.path.exists(keep):
        open(keep,"w").close()

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

def _esc(s: str) -> str:
    return (s or "").replace("\n", "\\n").replace('"', '\\"')

def _list_profiles() -> list[str]:
    names = []
    for fn in os.listdir(PROFILES_DIR):
        if fn.lower().endswith(".json"):
            names.append(os.path.splitext(fn)[0])
    names.sort()
    return names

def _slugify(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
    return slug or "business"

def _profile_path(name: str) -> str:
    return os.path.join(PROFILES_DIR, f"{_slugify(name)}.json")

def _logo_paths_for(name: str) -> list[str]:
    base = _slugify(name)
    out = []
    for ext in (".png",".jpg",".jpeg",".svg"):
        p = os.path.join(LOGOS_DIR, base+ext)
        if os.path.exists(p):
            out.append(p)
    return out

def _save_logo_for(name: str, file) -> str | None:
    if file is None:
        return None
    fname = getattr(file, "name", "logo.png")
    _, ext = os.path.splitext(fname.lower())
    if ext not in [".png",".jpg",".jpeg",".svg"]:
        ext = ".png"
    for existing in _logo_paths_for(name):
        try: os.remove(existing)
        except: pass
    dst = os.path.join(LOGOS_DIR, f"{_slugify(name)}{ext.lower()}")
    with open(dst, "wb") as f:
        f.write(file.read())
    return dst

def _load_logo_for(name: str) -> str | None:
    paths = _logo_paths_for(name)
    return paths[0] if paths else None

def _delete_profile_and_logo(name: str) -> None:
    try:
        os.remove(_profile_path(name))
    except FileNotFoundError:
        pass
    for p in _logo_paths_for(name):
        try: os.remove(p)
        except: pass

def build_graphviz_dot(business_name: str, revenue_goal: float, df: pd.DataFrame) -> str:
    business_label = f"{business_name}\\n12‑month Goal: ${revenue_goal:,.0f}"
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
            label = role if not person else f"{role}\\n({person})"
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

# ---------- Cached defaults ----------
@st.cache_data(show_spinner=False)
def empty_roles_df() -> pd.DataFrame:
    return pd.DataFrame(DEFAULT_ROWS, columns=ROLE_COLUMNS)

@st.cache_data(show_spinner=False)
def empty_streams_df() -> pd.DataFrame:
    return pd.DataFrame(DEFAULT_STREAMS, columns=REVENUE_COLUMNS)

@st.cache_data(show_spinner=False)
def csv_template() -> str:
    df = empty_roles_df()
    return df.to_csv(index=False)

def _default_people_costs(persons: list[str]) -> pd.DataFrame:
    return pd.DataFrame([{"Person": p, "AnnualCost": 0.0} for p in persons], columns=["Person","AnnualCost"])

def _default_monthly_plan(goal: float) -> pd.DataFrame:
    per = (goal or 0.0) / 12.0
    return pd.DataFrame({"Month": MONTHS, "PlannedRevenue": [per]*12})

def _default_monthly_actuals() -> pd.DataFrame:
    return pd.DataFrame({"Month": MONTHS, "RevenueActual": [0.0]*12, "CostOfSales": [0.0]*12, "OtherOverheads": [0.0]*12})

# ---------- App State Boot ----------
st.set_page_config(page_title="Success Dynamics – Accountability Chart", layout="wide", initial_sidebar_state="expanded")

if "functions" not in st.session_state: st.session_state.functions = CORE_FUNCTIONS.copy()
if "roles_df" not in st.session_state: st.session_state.roles_df = empty_roles_df()
if "revenue_streams_df" not in st.session_state: st.session_state.revenue_streams_df = empty_streams_df()
if "business_name" not in st.session_state: st.session_state.business_name = "My Business"
if "lock_goal" not in st.session_state: st.session_state.lock_goal = True
if "revenue_goal" not in st.session_state: st.session_state.revenue_goal = float(st.session_state.revenue_streams_df["TargetValue"].sum())
if "current_logo_path" not in st.session_state: st.session_state.current_logo_path = _load_logo_for(st.session_state.business_name)

# Tracking state
if "people_costs_df" not in st.session_state:
    uniq_people = sorted(set(st.session_state.roles_df["Person"].dropna().astype(str).str.strip()) - {""})
    st.session_state.people_costs_df = _default_people_costs(uniq_people)
if "monthly_plan_df" not in st.session_state:
    st.session_state.monthly_plan_df = _default_monthly_plan(st.session_state.revenue_goal)
if "monthly_actuals_df" not in st.session_state:
    st.session_state.monthly_actuals_df = _default_monthly_actuals()

# ---------- Sidebar: Admin ----------
with st.sidebar:
    st.markdown("### Admin")
    profiles = _list_profiles()
    selected = st.selectbox("Open business profile", options=["(none)"] + profiles, index=0)
    new_name = st.text_input("Business name", value=st.session_state.business_name)

    c_open, c_save, c_saveas = st.columns(3)
    with c_open:
        if st.button("Open"):
            if selected != "(none)":
                path = _profile_path(selected)
                try:
                    data = json.load(open(path, "r", encoding="utf-8"))
                    st.session_state.business_name = data.get("business", {}).get("name", selected)
                    st.session_state.functions = data.get("functions", CORE_FUNCTIONS).copy()
                    st.session_state.roles_df = pd.DataFrame(data.get("roles", []), columns=ROLE_COLUMNS) if data.get("roles") else empty_roles_df()
                    st.session_state.revenue_streams_df = pd.DataFrame(data.get("revenue_streams", DEFAULT_STREAMS), columns=REVENUE_COLUMNS)
                    st.session_state.revenue_goal = float(data.get("business", {}).get("revenue_goal", st.session_state.revenue_streams_df["TargetValue"].sum()))
                    st.session_state.lock_goal = bool(data.get("business", {}).get("lock_goal", True))
                    # tracking
                    pc = data.get("tracking", {}).get("people_costs", [])
                    st.session_state.people_costs_df = pd.DataFrame(pc, columns=["Person","AnnualCost"]) if pc else _default_people_costs([])
                    mp = data.get("tracking", {}).get("monthly_plan", [])
                    st.session_state.monthly_plan_df = pd.DataFrame(mp, columns=["Month","PlannedRevenue"]) if mp else _default_monthly_plan(st.session_state.revenue_goal)
                    ma = data.get("tracking", {}).get("monthly_actuals", [])
                    st.session_state.monthly_actuals_df = pd.DataFrame(ma, columns=["Month","RevenueActual","CostOfSales","OtherOverheads"]) if ma else _default_monthly_actuals()
                    st.session_state.current_logo_path = _load_logo_for(st.session_state.business_name)
                    st.success(f"Loaded profile: {selected}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to open: {e}")
    with c_save:
        if st.button("Save"):
            st.session_state.business_name = new_name.strip() or "My Business"
            export = {
                "business": {
                    "name": st.session_state.business_name,
                    "revenue_goal": st.session_state.revenue_goal,
                    "lock_goal": st.session_state.lock_goal,
                },
                "functions": st.session_state.functions,
                "roles": st.session_state.roles_df.fillna("").to_dict(orient="records"),
                "revenue_streams": st.session_state.revenue_streams_df.fillna("").to_dict(orient="records"),
                "tracking": {
                    "people_costs": st.session_state.people_costs_df.fillna(0).to_dict(orient="records"),
                    "monthly_plan": st.session_state.monthly_plan_df.fillna(0).to_dict(orient="records"),
                    "monthly_actuals": st.session_state.monthly_actuals_df.fillna(0).to_dict(orient="records"),
                }
            }
            try:
                with open(_profile_path(st.session_state.business_name), "w", encoding="utf-8") as f:
                    json.dump(export, f, indent=2)
                st.success(f"Saved: {st.session_state.business_name}")
                st.rerun()
            except Exception as e:
                st.error(f"Save failed: {e}")
    with c_saveas:
        if st.button("Save As"):
            name = new_name.strip() or "My Business"
            export = {
                "business": {
                    "name": name,
                    "revenue_goal": st.session_state.revenue_goal,
                    "lock_goal": st.session_state.lock_goal,
                },
                "functions": st.session_state.functions,
                "roles": st.session_state.roles_df.fillna("").to_dict(orient="records"),
                "revenue_streams": st.session_state.revenue_streams_df.fillna("").to_dict(orient="records"),
                "tracking": {
                    "people_costs": st.session_state.people_costs_df.fillna(0).to_dict(orient="records"),
                    "monthly_plan": st.session_state.monthly_plan_df.fillna(0).to_dict(orient="records"),
                    "monthly_actuals": st.session_state.monthly_actuals_df.fillna(0).to_dict(orient="records"),
                }
            }
            try:
                with open(_profile_path(name), "w", encoding="utf-8") as f:
                    json.dump(export, f, indent=2)
                st.session_state.business_name = name
                st.success(f"Saved As: {name}")
                st.rerun()
            except Exception as e:
                st.error(f"Save As failed: {e}")

    # Delete with confirmation
    st.markdown("---")
    st.markdown("### Danger Zone")
    confirm = st.checkbox("I understand this will permanently delete the selected profile and its logo(s).")
    if st.button("Delete Profile") and confirm:
        if selected == "(none)":
            st.warning("Select a profile to delete.")
        else:
            try:
                _delete_profile_and_logo(selected)
                st.success(f"Deleted profile: {selected}")
                if _slugify(selected) == _slugify(st.session_state.business_name):
                    st.session_state.business_name = "My Business"
                    st.session_state.functions = CORE_FUNCTIONS.copy()
                    st.session_state.roles_df = empty_roles_df()
                    st.session_state.revenue_streams_df = empty_streams_df()
                    st.session_state.revenue_goal = float(st.session_state.revenue_streams_df["TargetValue"].sum())
                    st.session_state.lock_goal = True
                    st.session_state.current_logo_path = None
                    st.session_state.people_costs_df = _default_people_costs([])
                    st.session_state.monthly_plan_df = _default_monthly_plan(st.session_state.revenue_goal)
                    st.session_state.monthly_actuals_df = _default_monthly_actuals()
                st.rerun()
            except Exception as e:
                st.error(f"Delete failed: {e}")

    # Branding
    st.markdown("---")
    st.markdown("### Branding")
    logo_file = st.file_uploader("Upload/Change logo", type=["png","jpg","jpeg","svg"], key="logo_uploader")
    if st.button("Attach Logo to Business"):
        target_name = new_name.strip() or st.session_state.business_name
        if logo_file is None:
            st.warning("Choose a logo file first.")
        else:
            path = _save_logo_for(target_name, logo_file)
            if path:
                st.session_state.business_name = target_name
                st.session_state.current_logo_path = path
                st.success("Logo saved to profile.")
                st.rerun()
            else:
                st.error("Logo save failed.")

    # Import/Export
    st.markdown("---")
    st.markdown("### Import / Export")
    uploaded_csv = st.file_uploader("Import Roles CSV", type=["csv"], key="csv")
    uploaded_json = st.file_uploader("Import JSON (full app data)", type=["json"], key="json")

    # Toggle goal behaviour
    st.session_state.lock_goal = st.checkbox("Lock revenue goal to sum of streams", value=st.session_state.lock_goal)

    # Tracking Quick Entry
    st.markdown("---")
    st.markdown("### Tracking – Quick Entry")
    q_month = st.selectbox("Month", options=MONTHS, index=0)
    q_rev   = st.number_input("Revenue (actual)", min_value=0.0, value=0.0, step=1000.0, format="%0.0f")
    q_cogs  = st.number_input("Cost of sales (COGS)", min_value=0.0, value=0.0, step=1000.0, format="%0.0f")
    q_oth   = st.number_input("Other overheads (this month)", min_value=0.0, value=0.0, step=1000.0, format="%0.0f")
    if st.button("Save Month Entry"):
        ma = st.session_state.monthly_actuals_df.set_index("Month")
        if q_month in ma.index:
            ma.at[q_month, "RevenueActual"] = q_rev
            ma.at[q_month, "CostOfSales"] = q_cogs
            ma.at[q_month, "OtherOverheads"] = q_oth
            st.session_state.monthly_actuals_df = ma.reset_index()
            st.success(f"Saved tracking for {q_month}")
        else:
            st.error("Month not found in table.")

# ---------- Header (Top) with Logo ----------
col_logo, col_title = st.columns([1,3], vertical_alignment="center")
with col_logo:
    if st.session_state.current_logo_path and os.path.exists(st.session_state.current_logo_path):
        st.image(st.session_state.current_logo_path, use_container_width=True)
    else:
        st.write("")  # spacer
with col_title:
    st.title("Accountability Chart Builder")
    st.caption("Success Dynamics — Profiles, Streams, Roles, Reporting Lines, Tracking")

# ---------- Revenue Streams ----------
st.subheader("Revenue Streams (12‑month)")
rev_df = st.session_state.revenue_streams_df
for c in REVENUE_COLUMNS:
    if c not in rev_df.columns: rev_df[c] = ""

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
if st.session_state.lock_goal:
    st.session_state.revenue_goal = streams_total
    st.caption("Revenue goal is locked to the sum of streams above.")
else:
    st.session_state.revenue_goal = st.number_input(
        "12‑month revenue goal ($)",
        min_value=0.0,
        value=max(1_000_000.0, streams_total),
        step=50_000.0, format="%0.0f"
    )

st.markdown("---")

# ---------- Functions / Roles ----------
col_left, col_right = st.columns([2,1])
with col_left:
    st.subheader("Functions")
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
                st.session_state.business_name = b.get("name", st.session_state.business_name)
                st.session_state.revenue_goal = float(b.get("revenue_goal", st.session_state.revenue_goal))
                st.session_state.lock_goal = bool(b.get("lock_goal", st.session_state.lock_goal))
            roles = data.get("roles", [])
            revs = data.get("revenue_streams", DEFAULT_STREAMS)
            st.session_state.revenue_streams_df = pd.DataFrame(revs, columns=REVENUE_COLUMNS)
            # tracking
            pc = data.get("tracking", {}).get("people_costs", [])
            st.session_state.people_costs_df = pd.DataFrame(pc, columns=["Person","AnnualCost"]) if pc else _default_people_costs([])
            mp = data.get("tracking", {}).get("monthly_plan", [])
            st.session_state.monthly_plan_df = pd.DataFrame(mp, columns=["Month","PlannedRevenue"]) if mp else _default_monthly_plan(st.session_state.revenue_goal)
            ma = data.get("tracking", {}).get("monthly_actuals", [])
            st.session_state.monthly_actuals_df = pd.DataFrame(ma, columns=["Month","RevenueActual","CostOfSales","OtherOverheads"]) if ma else _default_monthly_actuals()

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
        "Function": st.column_config.SelectboxColumn(options=st.session_state.functions, required=True),
        "FTE": st.column_config.NumberColumn(min_value=0.0, max_value=1.0, step=0.1, format="%0.1f"),
        "KPIs": st.column_config.TextColumn(help="Comma‑separated list"),
        "Accountabilities": st.column_config.TextColumn(help="Bullets or lines"),
    },
    hide_index=True,
    key="roles_editor",
)
st.session_state.roles_df = edited

st.markdown(":blue[Tip:] ‘ReportsTo’ should reference another *Role* name (not a person). Leave blank to attach directly under the Function header.")

st.markdown("---")

# ---------- Tracking (Setup & Dashboard) ----------
st.header("Tracking")

# People Costs setup (annual, per person)
# Initialise defaults from current roles if needed
current_people = sorted(set(st.session_state.roles_df["Person"].dropna().astype(str).str.strip()) - {""})
pc_df = st.session_state.people_costs_df
# Add missing people with 0 cost
missing_people = [p for p in current_people if p not in set(pc_df["Person"])]
if missing_people:
    pc_df = pd.concat([pc_df, pd.DataFrame([{"Person": p, "AnnualCost": 0.0} for p in missing_people])], ignore_index=True)
# Drop duplicates and non-assigned empty people
pc_df = pc_df.drop_duplicates(subset=["Person"]).reset_index(drop=True)
st.session_state.people_costs_df = pc_df

st.subheader("People Costs (Annual)")
pc_edit = st.data_editor(
    st.session_state.people_costs_df,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Person": st.column_config.TextColumn(required=True),
        "AnnualCost": st.column_config.NumberColumn(min_value=0.0, step=1000.0, format="%0.0f"),
    },
    hide_index=True,
    key="people_costs_editor",
)
st.session_state.people_costs_df = pc_edit
annual_people_cost_total = float(pc_edit["AnnualCost"].sum())
monthly_people_cost = annual_people_cost_total / 12.0
st.metric("Monthly fixed people cost", f"${monthly_people_cost:,.0f}")

# Monthly Plan (expected revenue per month)
st.subheader("Monthly Revenue Plan")
mp_df = st.session_state.monthly_plan_df
# Ensure it's 12 months, update if goal changed and plan is all zeros
if set(mp_df["Month"]) != set(MONTHS):
    mp_df = _default_monthly_plan(st.session_state.revenue_goal)
if mp_df["PlannedRevenue"].sum() == 0 and st.session_state.revenue_goal > 0:
    mp_df = _default_monthly_plan(st.session_state.revenue_goal)
mp_edit = st.data_editor(
    mp_df,
    num_rows=12,
    use_container_width=True,
    column_config={
        "Month": st.column_config.SelectboxColumn(options=MONTHS),
        "PlannedRevenue": st.column_config.NumberColumn(min_value=0.0, step=1000.0, format="%0.0f"),
    },
    hide_index=True,
    key="monthly_plan_editor",
)
st.session_state.monthly_plan_df = mp_edit

# Monthly Actuals
st.subheader("Monthly Actuals")
ma_df = st.session_state.monthly_actuals_df
# Ensure months align
if set(ma_df["Month"]) != set(MONTHS):
    ma_df = _default_monthly_actuals()
ma_edit = st.data_editor(
    ma_df,
    num_rows=12,
    use_container_width=True,
    column_config={
        "Month": st.column_config.SelectboxColumn(options=MONTHS),
        "RevenueActual": st.column_config.NumberColumn(min_value=0.0, step=1000.0, format="%0.0f"),
        "CostOfSales": st.column_config.NumberColumn(min_value=0.0, step=1000.0, format="%0.0f"),
        "OtherOverheads": st.column_config.NumberColumn(min_value=0.0, step=1000.0, format="%0.0f"),
    },
    hide_index=True,
    key="monthly_actuals_editor",
)
st.session_state.monthly_actuals_df = ma_edit

# Combine for dashboard
df_dash = mp_edit.merge(ma_edit, on="Month", how="left")
df_dash["PeopleFixed"] = monthly_people_cost
df_dash["GrossMargin"] = (df_dash["RevenueActual"] - df_dash["CostOfSales"]).fillna(0.0)
df_dash["OperatingProfit"] = (df_dash["GrossMargin"] - df_dash["PeopleFixed"] - df_dash["OtherOverheads"]).fillna(0.0)
df_dash = df_dash[["Month","PlannedRevenue","RevenueActual","CostOfSales","PeopleFixed","OtherOverheads","GrossMargin","OperatingProfit"]]

st.subheader("Dashboard")
# YTD: months with any actual revenue or any actual cost entered count as active months
mask_recorded = (df_dash["RevenueActual"]>0) | (df_dash["CostOfSales"]>0) | (df_dash["OtherOverheads"]>0)
months_recorded = int(mask_recorded.sum())
ytd_revenue = float(df_dash.loc[mask_recorded, "RevenueActual"].sum())
ytd_profit  = float(df_dash.loc[mask_recorded, "OperatingProfit"].sum())
projection_annual_revenue = (ytd_revenue / months_recorded * 12.0) if months_recorded > 0 else 0.0
projection_annual_profit  = (ytd_profit  / months_recorded * 12.0) if months_recorded > 0 else 0.0
colm1, colm2, colm3, colm4 = st.columns(4)
colm1.metric("Months recorded", months_recorded)
colm2.metric("YTD Revenue", f"${ytd_revenue:,.0f}")
colm3.metric("Annualised Revenue (run-rate)", f"${projection_annual_revenue:,.0f}")
colm4.metric("Annualised Profit (run-rate)", f"${projection_annual_profit:,.0f}")

# Charts
st.line_chart(df_dash.set_index("Month")[["PlannedRevenue","RevenueActual"]])
st.bar_chart(df_dash.set_index("Month")[["OperatingProfit"]])

st.markdown("---")

# ---------- Visualisation & Validation (Org Chart) ----------
st.subheader("Structure & Visualisation")
roles_ser = st.session_state.roles_df["Role"].fillna("").astype(str).str.strip()
if (roles_ser != "").sum() == 0:
    st.info("Add at least one Role to render the chart.")
else:
    dot = build_graphviz_dot(st.session_state.business_name, float(st.session_state.revenue_goal), st.session_state.roles_df)
    st.graphviz_chart(dot, use_container_width=True)

    dups = roles_ser[roles_ser != ""].duplicated(keep=False)
    dup_names = sorted(set(roles_ser[dups]))
    if dup_names:
        st.warning("Duplicate role names detected: " + ", ".join(dup_names) + ". Rename roles so each is unique.")

    rt = st.session_state.roles_df["ReportsTo"].fillna("").astype(str).str.strip()
    bad_refs = sorted(set(rt[(rt != "") & (~rt.isin(roles_ser))]))
    if bad_refs:
        st.warning("ReportsTo references missing: " + ", ".join(bad_refs) + ". Ensure each ‘ReportsTo’ matches an existing Role name.")

st.caption("© 2025 • Success Dynamics Accountability Chart • Streamlit app — v4")
