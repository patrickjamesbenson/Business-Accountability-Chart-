
import os, json, datetime as dt
from io import BytesIO
import pandas as pd
import streamlit as st

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
PROFILES_DIR = os.path.join(APP_ROOT, "data", "profiles")
LOGOS_DIR = os.path.join(APP_ROOT, "data", "logos")
os.makedirs(PROFILES_DIR, exist_ok=True)
os.makedirs(LOGOS_DIR, exist_ok=True)

st.set_page_config(page_title="Tracking Success (Lite v7.7b)", layout="wide")

def _slug(s): 
    import re
    return re.sub(r"[^A-Za-z0-9._-]+","_", s or "business").strip("_") or "business"

def list_profiles():
    return sorted([os.path.splitext(f)[0] for f in os.listdir(PROFILES_DIR) if f.endswith(".json")])

def save_profile(name, data):
    with open(os.path.join(PROFILES_DIR, f"{_slug(name)}.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_profile(name):
    p=os.path.join(PROFILES_DIR, f"{_slug(name)}.json")
    if os.path.exists(p):
        return json.loads(open(p,"r",encoding="utf-8").read())
    return None

def save_logo(name, file):
    if not file: return None
    import pathlib
    ext = os.path.splitext(file.name)[1].lower() or ".png"
    path = os.path.join(LOGOS_DIR, f"{_slug(name)}{ext}")
    pathlib.Path(path).write_bytes(file.read())
    return path

def find_logo(name):
    for ext in (".png",".jpg",".jpeg",".svg"):
        p=os.path.join(LOGOS_DIR, f"{_slug(name)}{ext}")
        if os.path.exists(p): return p
    return None

if "profile" not in st.session_state:
    st.session_state.profile = {
        "business": {"name":"My Business", "start_date": dt.date.today().isoformat()},
        "streams": [{"Stream":"New Clients","TargetValue":400000},{"Stream":"Subscriptions","TargetValue":300000},{"Stream":"Upsell","TargetValue":250000},{"Stream":"Other","TargetValue":50000}],
        "roles": [{"Function":"Sales & Marketing","Role":"","Person":""},{"Function":"Operations","Role":"","Person":""},{"Function":"Finance","Role":"","Person":""}],
        "people": [],  # Person, AnnualCost, HasVan(bool), ExtraMonthly
    }
if "logo_path" not in st.session_state:
    st.session_state.logo_path = None

# Header
cols = st.columns([1,3])
with cols[0]:
    if st.session_state.logo_path and os.path.exists(st.session_state.logo_path):
        st.image(st.session_state.logo_path)
with cols[1]:
    st.title("Tracking Success")
    st.caption("Lite v7.7b — Profiles • Streams • Roles • Trade Profit Calculator")

# Sidebar Admin
with st.sidebar:
    st.subheader("Admin")
    profiles = list_profiles()
    open_sel = st.selectbox("Open profile", ["(none)"]+profiles)
    if st.button("Open"):
        if open_sel != "(none)":
            prof = load_profile(open_sel)
            if prof:
                st.session_state.profile = prof
                st.session_state.logo_path = find_logo(prof["business"]["name"])
                st.success(f"Opened {open_sel}")
                st.rerun()
    st.divider()
    st.text_input("Business name", value=st.session_state.profile["business"]["name"], key="biz_name")
    st.date_input("Account start date", value=dt.date.fromisoformat(st.session_state.profile["business"].get("start_date", dt.date.today().isoformat())), key="biz_start")
    logo = st.file_uploader("Upload logo", type=["png","jpg","jpeg","svg"])
    if st.button("Attach Logo"):
        if logo:
            path = save_logo(st.session_state.biz_name, logo)
            st.session_state.logo_path = path
            st.session_state.profile["business"]["name"] = st.session_state.biz_name
            st.session_state.profile["business"]["start_date"] = st.session_state.biz_start.isoformat()
            save_profile(st.session_state.biz_name, st.session_state.profile)
            st.success("Logo attached & profile saved.")
            st.rerun()
        else:
            st.warning("Choose a logo first.")
    c1,c2 = st.columns(2)
    with c1:
        if st.button("Save"):
            st.session_state.profile["business"]["name"] = st.session_state.biz_name
            st.session_state.profile["business"]["start_date"] = st.session_state.biz_start.isoformat()
            save_profile(st.session_state.biz_name, st.session_state.profile)
            st.success("Saved.")
    with c2:
        new_as = st.text_input("Save As…", key="saveas_name", placeholder="New business name")
        if st.button("Save As"):
            nm = new_as.strip() or st.session_state.biz_name
            st.session_state.profile["business"]["name"] = nm
            st.session_state.profile["business"]["start_date"] = st.session_state.biz_start.isoformat()
            save_profile(nm, st.session_state.profile)
            st.success(f"Saved as {nm}")

# Streams
with st.expander("Revenue Streams", expanded=False):
    df = pd.DataFrame(st.session_state.profile.get("streams", []))
    if df.empty:
        df = pd.DataFrame([{"Stream":"", "TargetValue":0.0}], columns=["Stream","TargetValue"])
    df["TargetValue"] = pd.to_numeric(df["TargetValue"], errors="coerce").fillna(0.0)
    edited = st.data_editor(df, num_rows="dynamic", use_container_width=True, hide_index=True,
                            column_config={"Stream": st.column_config.TextColumn(), "TargetValue": st.column_config.NumberColumn(format="%.0f")})
    st.session_state.profile["streams"] = edited.fillna("").to_dict(orient="records")
    st.metric("Total Target", f"${edited['TargetValue'].sum():,.0f}")

# Roles
with st.expander("Organisation — Functions & Roles", expanded=False):
    df = pd.DataFrame(st.session_state.profile.get("roles", []))
    if df.empty:
        df = pd.DataFrame([{"Function":"Sales & Marketing","Role":"","Person":""}], columns=["Function","Role","Person"])
    edited = st.data_editor(df, num_rows="dynamic", use_container_width=True, hide_index=True)
    st.session_state.profile["roles"] = edited.fillna("").to_dict(orient="records")

# People costs
with st.expander("People Costs (annual) & Vans", expanded=False):
    ppl = pd.DataFrame(st.session_state.profile.get("people", []))
    if ppl.empty:
        ppl = pd.DataFrame([{"Person":"Tradie 1","AnnualCost":90000.0,"HasVan":True,"ExtraMonthly":1200.0},
                            {"Person":"Apprentice 1","AnnualCost":60000.0,"HasVan":False,"ExtraMonthly":0.0}], 
                            columns=["Person","AnnualCost","HasVan","ExtraMonthly"])
    ppl["AnnualCost"] = pd.to_numeric(ppl["AnnualCost"], errors="coerce").fillna(0.0)
    ppl["ExtraMonthly"] = pd.to_numeric(ppl["ExtraMonthly"], errors="coerce").fillna(0.0)
    edited = st.data_editor(ppl, num_rows="dynamic", use_container_width=True, hide_index=True,
                            column_config={
                                "Person": st.column_config.TextColumn(),
                                "AnnualCost": st.column_config.NumberColumn(format="%.0f"),
                                "HasVan": st.column_config.CheckboxColumn(),
                                "ExtraMonthly": st.column_config.NumberColumn(format="%.0f", help="Use for van cost or extras")
                            })
    st.session_state.profile["people"] = edited.fillna("").to_dict(orient="records")

# --- Trade Profit Calculator (beta) ---
st.header("Trade Profit Calculator (beta)")
st.caption("Estimate the blended hourly rate required to hit your profit target based on team, utilisation, quotes→jobs, materials %, marketing, and overheads.")

import math
colA,colB,colC = st.columns(3)
with colA:
    weeks = st.number_input("Weeks in period", min_value=1.0, value=4.33, step=0.25)
with colB:
    mat_pct = st.number_input("Materials (COGS) % of revenue", min_value=0.0, max_value=95.0, value=25.0, step=1.0)
with colC:
    current_rate = st.number_input("Your current blended rate ($/hr)", min_value=0.0, value=120.0, step=5.0)

st.subheader("Team")
team = pd.DataFrame([
    {"Person":"Tradie 1","Role":"Tradie","HourlyWageCost":40.0,"VanMonthly":1200.0,"PaidHoursPerWeek":38.0,"UtilisationPct":70.0,"QuotesPerWeek":3.0,"QuoteToJobPct":40.0,"AvgJobHours":2.0},
    {"Person":"Apprentice 1","Role":"Apprentice","HourlyWageCost":25.0,"VanMonthly":0.0,"PaidHoursPerWeek":38.0,"UtilisationPct":65.0,"QuotesPerWeek":1.0,"QuoteToJobPct":35.0,"AvgJobHours":1.5},
])
team = st.data_editor(team, num_rows="dynamic", use_container_width=True, hide_index=True)
team = team.fillna(0.0)

st.subheader("Overheads per month")
col1,col2 = st.columns(2)
with col1:
    mkt = st.number_input("Marketing spend ($/month)", min_value=0.0, value=2000.0, step=100.0)
with col2:
    other = st.number_input("Other fixed overheads ($/month)", min_value=0.0, value=8000.0, step=100.0)

st.subheader("Target")
t1,t2,t3 = st.columns(3)
with t1:
    hours_source = st.selectbox("Use hours from", ["Capacity (utilisation)","Demand (quotes→jobs)"])
with t2:
    target_mode = st.selectbox("Target type", ["Profit $","Profit Margin %"])
with t3:
    target_profit = st.number_input("Target profit for period ($)", min_value=0.0, value=10000.0, step=500.0)
margin_pct = st.slider("Target margin % (if using margin)", min_value=0, max_value=70, value=20, step=1)

# Calculations
team["PaidHoursPeriod"] = team["PaidHoursPerWeek"] * weeks
team["BillableHoursPeriod"] = team["PaidHoursPeriod"] * (team["UtilisationPct"]/100.0)
team["JobsFromQuotes"] = (team["QuotesPerWeek"] * weeks) * (team["QuoteToJobPct"]/100.0)
team["BillableFromJobs"] = team["JobsFromQuotes"] * team["AvgJobHours"]
H = float(team["BillableHoursPeriod"].sum()) if hours_source.startswith("Capacity") else float(team["BillableFromJobs"].sum())

team["WageCostPeriod"] = team["HourlyWageCost"] * team["PaidHoursPeriod"]
team["VanCostPeriod"]  = team["VanMonthly"] * (weeks/4.33)
people_costs = float((team["WageCostPeriod"] + team["VanCostPeriod"]).sum())
mkt_p = mkt * (weeks/4.33)
oth_p = other * (weeks/4.33)
m = mat_pct/100.0

if target_mode=="Profit $":
    required_rate = ((target_profit + people_costs + mkt_p + oth_p) / max(H*(1-m), 1e-6)) if H>0 else 0.0
else:
    M = margin_pct/100.0
    denom = (1 - m - M)
    required_rate = ((people_costs + mkt_p + oth_p) / max(H*denom, 1e-6)) if H>0 else 0.0

revenue_at_current = current_rate * H
profit_at_current  = revenue_at_current - (m*revenue_at_current) - people_costs - mkt_p - oth_p
margin_at_current  = (profit_at_current/revenue_at_current*100.0) if revenue_at_current>0 else 0.0

s1,s2,s3 = st.columns(3)
with s1:
    st.metric("Billable hours (period)", f"{H:,.1f}")
with s2:
    st.metric("Required blended rate", f"${required_rate:,.2f}/hr")
with s3:
    st.metric("At current rate", f"Profit ${profit_at_current:,.0f} ({margin_at_current:,.1f}%)")

# Per person contribution at required rate
st.subheader("Per-person contribution (at required rate)")
share = team[["Person","BillableHoursPeriod" if hours_source.startswith("Capacity") else "BillableFromJobs"]].copy()
share = share.rename(columns={"BillableHoursPeriod":"BillableHrs","BillableFromJobs":"BillableHrs"})
share["RevenueAtRequired"] = required_rate * share["BillableHrs"]
share["WageCostPeriod"] = team["WageCostPeriod"]
share["VanCostPeriod"]  = team["VanCostPeriod"]
tot_rev = float(share["RevenueAtRequired"].sum())
if tot_rev>0:
    share["COGS"] = m * share["RevenueAtRequired"]
    share["OverheadsAlloc"] = (mkt_p + oth_p) * (share["RevenueAtRequired"]/tot_rev)
else:
    share["COGS"] = 0.0
    share["OverheadsAlloc"] = 0.0
share["Profit"] = share["RevenueAtRequired"] - share["COGS"] - share["WageCostPeriod"] - share["VanCostPeriod"] - share["OverheadsAlloc"]
st.dataframe(share, use_container_width=True)

st.divider()
st.caption("Lite build. For full v7.x features (PDFs, tasks, mission/values, journey, webhooks, etc.), ask to regenerate the full bundle.")
