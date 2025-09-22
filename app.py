# app.py — Success Dynamics Accountability Chart (Streamlit) — v3
# ----------------------------------------------------------------
# New in v3:
# - Delete Profile (also deletes linked logo files)
# - Attach / Change Logo per profile (overwrite supported)
# - Auto-rerun on Open/Save/Save As/Attach Logo/Delete Profile to refresh header + state
# - Data folders include .gitkeep so GitHub drag-drop keeps folder structure
#
from __future__ import annotations

import json, os, re, shutil
from io import StringIO
from typing import Dict, List, Any

import pandas as pd
import streamlit as st

# ---------- Constants & Helpers ----------
CORE_FUNCTIONS = ["Sales & Marketing", "Operations", "Finance"]
ROLE_COLUMNS = ["Function","Role","Person","FTE","ReportsTo","KPIs","Accountabilities","Notes"]
REVENUE_COLUMNS = ["Stream","TargetValue","Notes"]

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
    # Safe filename
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
    # Detect extension
    fname = getattr(file, "name", "logo.png")
    _, ext = os.path.splitext(fname.lower())
    if ext not in [".png",".jpg",".jpeg",".svg"]:
        ext = ".png"
    # Remove any existing logo variants for this profile (so we don't keep multiple)
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
    # Delete JSON
    try:
        os.remove(_profile_path(name))
    except FileNotFoundError:
        pass
    # Delete logo(s)
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

# ---------- App State Boot ----------
st.set_page_config(page_title="Success Dynamics – Accountability Chart", layout="wide", initial_sidebar_state="expanded")

if "functions" not in st.session_state: st.session_state.functions = CORE_FUNCTIONS.copy()
if "roles_df" not in st.session_state: st.session_state.roles_df = empty_roles_df()
if "revenue_streams_df" not in st.session_state: st.session_state.revenue_streams_df = empty_streams_df()
if "business_name" not in st.session_state: st.session_state.business_name = "My Business"
if "lock_goal" not in st.session_state: st.session_state.lock_goal = True
if "revenue_goal" not in st.session_state: st.session_state.revenue_goal = float(st.session_state.revenue_streams_df["TargetValue"].sum())
if "current_logo_path" not in st.session_state: st.session_state.current_logo_path = _load_logo_for(st.session_state.business_name)

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
                # If deleting the current profile, reset to defaults
                if _slugify(selected) == _slugify(st.session_state.business_name):
                    st.session_state.business_name = "My Business"
                    st.session_state.functions = CORE_FUNCTIONS.copy()
                    st.session_state.roles_df = empty_roles_df()
                    st.session_state.revenue_streams_df = empty_streams_df()
                    st.session_state.revenue_goal = float(st.session_state.revenue_streams_df["TargetValue"].sum())
                    st.session_state.lock_goal = True
                    st.session_state.current_logo_path = None
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

# ---------- Header (Top) with Logo ----------
col_logo, col_title = st.columns([1,3], vertical_alignment="center")
with col_logo:
    if st.session_state.current_logo_path and os.path.exists(st.session_state.current_logo_path):
        st.image(st.session_state.current_logo_path, use_container_width=True)
    else:
        st.write("")  # spacer
with col_title:
    st.title("Accountability Chart Builder")
    st.caption("Success Dynamics — Profiles, Streams, Roles, Reporting Lines")

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

# Quick exports
colA, colB = st.columns(2)
with colA:
    export_data = {
        "business": {
            "name": st.session_state.business_name,
            "revenue_goal": st.session_state.revenue_goal,
            "lock_goal": st.session_state.lock_goal,
        },
        "functions": st.session_state.functions,
        "roles": st.session_state.roles_df.fillna("").to_dict(orient="records"),
        "revenue_streams": st.session_state.revenue_streams_df.fillna("").to_dict(orient="records"),
    }
    st.download_button("Export JSON (current)", data=json.dumps(export_data, indent=2), file_name="accountability_chart.json", mime="application/json")
with colB:
    from io import StringIO as _SIO
    csv_buf = _SIO()
    st.session_state.roles_df.to_csv(csv_buf, index=False)
    st.download_button("Export Roles CSV", data=csv_buf.getvalue(), file_name="accountability_chart_roles.csv", mime="text/csv")

st.markdown("---")

# ---------- Visualisation & Validation ----------
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

st.caption("© 2025 • Success Dynamics Accountability Chart • Streamlit app — v3")
