
# Tracking Success — Full v7.7c
# Profiles • Logos • Streams • Org • People (vans) • Start date • Tracking & Dashboard
# Coaching notes (screenshots/URLs with include-in-report) • Tasks with completion links
# PDFs (Tracking & Details) • Push Sync (UpCoach webhook, Calendly helper, Email SMTP)
# Customer Journey Mapping • Mission & Values • Trade Profit Calculator

from __future__ import annotations
import os, re, json, math, calendar, tempfile, uuid, datetime as dt
from io import BytesIO
from typing import Optional, List, Dict, Any

import pandas as pd
import streamlit as st

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# PDF (reportlab)
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak

# Optional outbound
try:
    import requests
except Exception:
    requests = None

try:
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
except Exception:
    smtplib = None

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
PROFILES_DIR = os.path.join(APP_ROOT, "data", "profiles")
LOGOS_DIR    = os.path.join(APP_ROOT, "data", "logos")
ASSETS_DIR   = os.path.join(APP_ROOT, "data", "assets")
for d in (PROFILES_DIR, LOGOS_DIR, ASSETS_DIR):
    os.makedirs(d, exist_ok=True)

MONTHS = list(calendar.month_name)[1:]  # Jan..Dec
CUR_YEAR = dt.date.today().year
CORE_FUNCTIONS = ["Sales & Marketing", "Operations", "Finance"]
ROLE_COLUMNS = ["Function","Role","Person","FTE","ReportsTo","KPIs","Accountabilities","Notes"]
REVENUE_COLUMNS = ["Stream","TargetValue","Notes"]

# ---------- Helpers ----------
def _slug(name: str)->str:
    return re.sub(r"[^A-Za-z0-9._-]+","_", (name or "business")).strip("_") or "business"

def storage_list_profiles()->list[str]:
    return sorted([os.path.splitext(f)[0] for f in os.listdir(PROFILES_DIR) if f.lower().endswith(".json")])

def storage_read_profile(name: str)->Optional[dict]:
    p=os.path.join(PROFILES_DIR, f"{_slug(name)}.json")
    if os.path.exists(p):
        return json.loads(open(p,"r",encoding="utf-8").read())
    return None

def storage_write_profile(name: str, data: dict)->bool:
    try:
        with open(os.path.join(PROFILES_DIR, f"{_slug(name)}.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False

def storage_save_logo(name: str, file)->Optional[str]:
    if file is None: return None
    base=_slug(name); ext=os.path.splitext(getattr(file,"name","logo.png"))[1].lower()
    if ext not in (".png",".jpg",".jpeg",".svg"): ext=".png"
    dst=os.path.join(LOGOS_DIR, f"{base}{ext}")
    open(dst,"wb").write(file.read())
    return dst

def storage_load_logo_path(name: str)->Optional[str]:
    base=_slug(name)
    for ext in (".png",".jpg",".jpeg",".svg"):
        p=os.path.join(LOGOS_DIR, f"{base}{ext}")
        if os.path.exists(p): return p
    return None

def default_streams()->list[dict]:
    return [
        {"Stream":"New Clients","TargetValue":400000,"Notes":""},
        {"Stream":"Subscriptions / Recurring","TargetValue":300000,"Notes":""},
        {"Stream":"Upsell (New Program)","TargetValue":250000,"Notes":""},
        {"Stream":"Other / Experiments","TargetValue":50000,"Notes":""},
    ]

def months_from_start(start_date_iso: str)->list[str]:
    """Return MONTHS reordered to start at account start month."""
    try:
        m = dt.date.fromisoformat(start_date_iso).month
    except Exception:
        m = 1
    idx = m-1
    return MONTHS[idx:] + MONTHS[:idx]

def default_monthly_plan(goal: float, start_date_iso: str)->list[dict]:
    months = months_from_start(start_date_iso)
    per = float(goal or 0.0)/12.0
    return [{"Month": m, "PlannedRevenue": per} for m in months]

def default_monthly_actuals(start_date_iso: str)->list[dict]:
    months = months_from_start(start_date_iso)
    return [{"Month": m, "RevenueActual":0.0, "CostOfSales":0.0, "OtherOverheads":0.0} for m in months]

def ensure_year(profile: dict, year: int)->dict:
    years = profile.setdefault("years", {})
    ykey = str(year)
    if ykey not in years:
        start = profile.get("business",{}).get("start_date", dt.date.today().isoformat())
        goal = 0.0
        years[ykey] = {
            "revenue_goal": goal,
            "lock_goal": True,
            "revenue_streams": default_streams(),
            "people_costs": [],  # Person, AnnualCost, StartMonth(1-12), HasVan, Comment, ExtraMonthly
            "van_monthly_default": 1200.0,
            "monthly_plan": default_monthly_plan(goal, start),
            "monthly_actuals": default_monthly_actuals(start),
            "accountability": {m: [] for m in MONTHS},  # not rotated; month names for notes
            "next_session": {},
            "coaching_assets": {},  # month -> {images:[{path,caption,include}], links:[{url,caption,include}]}
            "tasks": [],  # {id,title,assignee,due,status,include_in_report,notes,token}
            "mission_values": {"mission":"","values":[],"principles":[],"trust_model":"Earned","prompts":{}},
            "data_sources": [],  # [{name,url}]
            "account_start_date": start,
            "horizon_goals": {"M1":None,"M3":None,"M6":None,"M12":None},
        }
    return profile

def people_monthly_costs(people_costs: list[dict], van_default: float, months_seq: list[str])->dict:
    """Return month->people_cost for 12 months in the displayed order.
       AnnualCost spread evenly; person counted from StartMonth onwards.
       ExtraMonthly always added (van etc) when counted.
    """
    # map month name to index 1..12 Jan=1
    name_to_idx = {m:i+1 for i,m in enumerate(MONTHS)}
    costs = {m:0.0 for m in months_seq}
    for p in people_costs or []:
        startm = int(p.get("StartMonth",1) or 1)
        annual = float(p.get("AnnualCost",0.0) or 0.0)
        extra  = float(p.get("ExtraMonthly", 0.0) or 0.0)
        has_van= bool(p.get("HasVan", False))
        for m in months_seq:
            mi = name_to_idx[m]
            # Treat "StartMonth" relative to calendar (Jan=1). We include cost if month index >= startm.
            if mi >= startm:
                costs[m] += (annual/12.0) + (extra if extra else (van_default if has_van else 0.0))
    return costs

def infer_cogs_pct(df: pd.DataFrame)->float:
    # infer from actuals with revenue > 0; else default 25%
    vals = []
    for _,r in df.iterrows():
        rev=float(r.get("RevenueActual",0.0) or 0.0); c=float(r.get("CostOfSales",0.0) or 0.0)
        if rev>0: vals.append(c/rev)
    if vals:
        pct = sum(vals)/len(vals)
        return max(0.0, min(0.95, pct))
    return 0.25

def build_dashboard_df(yb: dict)->pd.DataFrame:
    start = yb.get("account_start_date", dt.date.today().isoformat())
    months_seq = months_from_start(start)
    mp = pd.DataFrame(yb.get("monthly_plan", default_monthly_plan(yb.get("revenue_goal",0.0), start)))
    ma = pd.DataFrame(yb.get("monthly_actuals", default_monthly_actuals(start)))
    df = mp.merge(ma, on="Month", how="left").fillna(0.0)
    # people monthly
    people_m = people_monthly_costs(yb.get("people_costs", []), float(yb.get("van_monthly_default",1200.0)), months_seq)
    df["PeopleMonthly"] = df["Month"].map(people_m).fillna(0.0)
    # break-even using inferred COGS%
    cogs_pct = infer_cogs_pct(df)
    df["BreakEvenRevenue"] = df["PeopleMonthly"] + df["OtherOverheads"]
    df["BreakEvenRevenue"] = df["BreakEvenRevenue"] / max(1e-6, (1.0 - cogs_pct))
    # operating profit
    df["OperatingProfit"] = df["RevenueActual"] - df["CostOfSales"] - df["PeopleMonthly"] - df["OtherOverheads"]
    df["MarginPct"] = df.apply(lambda r: (r["OperatingProfit"]/r["RevenueActual"]*100.0) if r["RevenueActual"]>0 else None, axis=1)
    return df

def fig_to_buf(fig)->bytes:
    out=BytesIO(); fig.savefig(out, format="png", bbox_inches="tight", dpi=160); plt.close(fig); return out.getvalue()

def build_tracking_pdf(profile: dict, year:int, df_dash: pd.DataFrame, logo_path: Optional[str],
                       accountability: dict, next_session: dict, assets: dict, tasks: list[dict])->bytes:
    buf=BytesIO()
    doc=SimpleDocTemplate(buf, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=48, bottomMargin=36)
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name="H1", fontName="Helvetica-Bold", fontSize=18, spaceAfter=12))
    styles.add(ParagraphStyle(name="H2", fontName="Helvetica-Bold", fontSize=13, spaceAfter=8))
    styles.add(ParagraphStyle(name="Body", fontName="Helvetica", fontSize=10, leading=13))
    elems=[]
    title=f"{profile['business'].get('name','Business')} — Tracking Report {year}"
    elems.append(Paragraph(title, styles["H1"]))
    if logo_path and os.path.exists(logo_path):
        try: elems.append(RLImage(logo_path, width=120, height=40)); elems.append(Spacer(1,6))
        except Exception: pass

    # Summary
    ytd_rev=float(df_dash["RevenueActual"].sum())
    ytd_profit=float(df_dash["OperatingProfit"].sum())
    months_recorded=int(((df_dash["RevenueActual"]>0)|(df_dash["CostOfSales"]>0)|(df_dash["OtherOverheads"]>0)).sum())
    goal=float(profile.get("years",{}).get(str(year),{}).get("revenue_goal",0.0))
    runrate_rev=(ytd_rev/months_recorded*12.0) if months_recorded>0 else 0.0
    runrate_profit=(ytd_profit/months_recorded*12.0) if months_recorded>0 else 0.0
    t=Table([["Revenue Goal", f"${goal:,.0f}", "Months Recorded", f"{months_recorded}"],
             ["YTD Revenue", f"${ytd_rev:,.0f}", "Annualised Revenue (run‑rate)", f"${runrate_rev:,.0f}"],
             ["YTD Profit",  f"${ytd_profit:,.0f}", "Annualised Profit (run‑rate)",  f"${runrate_profit:,.0f}"]], hAlign="LEFT")
    t.setStyle(TableStyle([("FONT",(0,0),(-1,-1),"Helvetica",10),("BACKGROUND",(0,0),(-1,0), colors.whitesmoke),("GRID",(0,0),(-1,-1),0.25, colors.lightgrey)]))
    elems.append(t); elems.append(Spacer(1,8))

    # Charts
    fig1, ax = plt.subplots(figsize=(7.2,3))
    x=list(range(len(df_dash)))
    ax.plot(x, df_dash["PlannedRevenue"], marker="")
    ax.plot(x, df_dash["RevenueActual"], marker="")
    ax.plot(x, df_dash["BreakEvenRevenue"], marker="")
    ax.set_xticks(x); ax.set_xticklabels(df_dash["Month"], rotation=45, ha="right")
    ax.set_ylabel("Revenue ($)"); ax.legend(["Planned","Actual","Break‑even"])
    elems.append(RLImage(BytesIO(fig_to_buf(fig1)), width=500, height=200)); elems.append(Spacer(1,6))

    fig2, ax1 = plt.subplots(figsize=(7.2,3))
    ax1.bar(x, df_dash["OperatingProfit"].fillna(0.0))
    ax1.set_xticks(x); ax1.set_xticklabels(df_dash["Month"], rotation=45, ha="right")
    ax1.set_ylabel("Operating Profit ($)")
    ax2=ax1.twinx(); ax2.plot(x, [m if m is not None else float('nan') for m in df_dash["MarginPct"]], marker="o")
    ax2.set_ylabel("Margin %")
    elems.append(RLImage(BytesIO(fig_to_buf(fig2)), width=500, height=200))

    # Assets included
    elems.append(PageBreak())
    elems.append(Paragraph("Coaching Evidence — Included", styles["H2"]))
    rows=[["Month","Type","Item"]]
    thumb_rows=[]
    for m, pack in (assets or {}).items():
        for ln in (pack.get("links") or []):
            if ln.get("include"):
                rows.append([m, "URL", f"{ln.get('url','')} — {ln.get('caption','')}"])
        for im in (pack.get("images") or []):
            if im.get("include"):
                rows.append([m, "Image", im.get("caption","(screenshot)")])
                path=im.get("path")
                if path and os.path.exists(path):
                    thumb_rows.append([m, RLImage(path, width=180, height=110), im.get("caption","")])
    if len(rows)==1: rows.append(["—","—","—"])
    tassets=Table(rows, hAlign="LEFT", colWidths=[65,60,300])
    tassets.setStyle(TableStyle([("FONT",(0,0),(-1,-1),"Helvetica",8),("BACKGROUND",(0,0),(-1,0), colors.whitesmoke),("GRID",(0,0),(-1,-1),0.25, colors.lightgrey)]))
    elems.append(tassets); elems.append(Spacer(1,8))
    if thumb_rows:
        elems.append(Paragraph("Thumbnails", styles["H2"]))
        tthumb=Table([["Month","Image","Caption"]]+thumb_rows, colWidths=[60,200,290])
        tthumb.setStyle(TableStyle([("FONT",(0,0),(-1,-1),"Helvetica",8),("GRID",(0,0),(-1,-1),0.25, colors.lightgrey),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
        elems.append(tthumb); elems.append(Spacer(1,6))

    # Accountability
    elems.append(Paragraph("Accountability (by month)", styles["H2"]))
    rows=[["Month","Action","Owner","Due","Status","Notes"]]
    for m in MONTHS:
        for it in accountability.get(m, []):
            rows.append([m,it.get("action",""),it.get("owner",""),it.get("due",""),it.get("status",""),it.get("notes","")])
    if len(rows)==1: rows.append(["—","—","—","—","—","—"])
    t2=Table(rows, hAlign="LEFT", colWidths=[65,200,70,55,60,130])
    t2.setStyle(TableStyle([("FONT",(0,0),(-1,-1),"Helvetica",8),("BACKGROUND",(0,0),(-1,0), colors.whitesmoke),("GRID",(0,0),(-1,-1),0.25, colors.lightgrey)]))
    elems.append(t2); elems.append(Spacer(1,6))

    # Tasks included
    elems.append(Paragraph("Tasks (included)", styles["H2"]))
    rows=[["Title","Assignee","Due","Status","Notes"]]
    for tsk in tasks or []:
        if not tsk.get("include_in_report"): continue
        rows.append([tsk.get("title",""), tsk.get("assignee",""), tsk.get("due",""), tsk.get("status","Planned"), tsk.get("notes","")])
    if len(rows)==1: rows.append(["—","—","—","—","—"])
    t3=Table(rows, hAlign="LEFT", colWidths=[160,80,70,60,160])
    t3.setStyle(TableStyle([("FONT",(0,0),(-1,-1),"Helvetica",8),("BACKGROUND",(0,0),(-1,0), colors.whitesmoke),("GRID",(0,0),(-1,-1),0.25, colors.lightgrey)]))
    elems.append(t3)

    doc.build(elems); return buf.getvalue()

def build_details_pdf(profile: dict, year:int, include_flags: dict, logo_path: Optional[str])->bytes:
    buf=BytesIO()
    doc=SimpleDocTemplate(buf, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=48, bottomMargin=36)
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name="H1", fontName="Helvetica-Bold", fontSize=18, spaceAfter=12))
    styles.add(ParagraphStyle(name="H2", fontName="Helvetica-Bold", fontSize=13, spaceAfter=8))
    styles.add(ParagraphStyle(name="Body", fontName="Helvetica", fontSize=10, leading=13))
    elems=[]
    title=f"{profile['business'].get('name','Business')} — Details {year}"
    elems.append(Paragraph(title, styles["H1"]))
    if logo_path and os.path.exists(logo_path):
        try: elems.append(RLImage(logo_path, width=120, height=40)); elems.append(Spacer(1,6))
        except Exception: pass
    yb=profile.get("years",{}).get(str(year),{})
    goal=float(yb.get("revenue_goal",0.0))
    start = yb.get("account_start_date")
    elems.append(Paragraph(f"Revenue Goal: <b>${goal:,.0f}</b>", styles["Body"]))
    if start: elems.append(Paragraph(f"Account Start Date: <b>{start}</b>", styles["Body"])); elems.append(Spacer(1,6))

    if include_flags.get("streams"):
        elems.append(Paragraph("Revenue Streams", styles["H2"]))
        df=pd.DataFrame(yb.get("revenue_streams", []))
        if not df.empty:
            data=[["Stream","TargetValue","Notes"]]+df.fillna("").values.tolist()
            t=Table(data, hAlign="LEFT", colWidths=[220,100,160])
            t.setStyle(TableStyle([("FONT",(0,0),(-1,-1),"Helvetica",10),("BACKGROUND",(0,0),(-1,0), colors.whitesmoke),("GRID",(0,0),(-1,-1),0.25, colors.lightgrey)]))
            elems.append(t); elems.append(Spacer(1,6))

    if include_flags.get("roles"):
        elems.append(Paragraph("Organisation: Functions & Roles", styles["H2"]))
        roles=pd.DataFrame(profile.get("roles", []))
        if not roles.empty:
            cols=["Function","Role","Person","FTE","ReportsTo","KPIs"]
            roles=roles[cols].fillna("")
            data=[cols]+roles.values.tolist()
            t=Table(data, hAlign="LEFT", colWidths=[110,120,100,40,100,120])
            t.setStyle(TableStyle([("FONT",(0,0),(-1,-1),"Helvetica",9),("BACKGROUND",(0,0),(-1,0), colors.whitesmoke),("GRID",(0,0),(-1,-1),0.25, colors.lightgrey)]))
            elems.append(t); elems.append(Spacer(1,6))

    if include_flags.get("people"):
        elems.append(Paragraph("People Costs (Annual)", styles["H2"]))
        pc=pd.DataFrame(yb.get("people_costs", []))
        if not pc.empty:
            data=[["Person","AnnualCost","StartMonth","HasVan","Comment","ExtraMonthly"]]+pc.fillna("").values.tolist()
            t=Table(data, hAlign="LEFT", colWidths=[120,80,60,50,140,70])
            t.setStyle(TableStyle([("FONT",(0,0),(-1,-1),"Helvetica",9),("BACKGROUND",(0,0),(-1,0), colors.whitesmoke),("GRID",(0,0),(-1,-1),0.25, colors.lightgrey)]))
            elems.append(t); elems.append(Spacer(1,6))

    if include_flags.get("monthly"):
        elems.append(Paragraph("Monthly Plan & Actuals", styles["H2"]))
        mp=pd.DataFrame(yb.get("monthly_plan", [])); ma=pd.DataFrame(yb.get("monthly_actuals", []))
        dfm=mp.merge(ma, on="Month", how="left")[["Month","PlannedRevenue","RevenueActual","CostOfSales","OtherOverheads"]].fillna(0.0)
        data=[list(dfm.columns)]+dfm.values.tolist()
        t=Table(data, hAlign="LEFT", colWidths=[80,100,100,100,100])
        t.setStyle(TableStyle([("FONT",(0,0),(-1,-1),"Helvetica",8),("BACKGROUND",(0,0),(-1,0), colors.whitesmoke),("GRID",(0,0),(-1,-1),0.25, colors.lightgrey)]))
        elems.append(t)

    mv = yb.get("mission_values", {})
    if mv and (mv.get("mission") or mv.get("values") or mv.get("principles")):
        elems.append(Spacer(1,8))
        elems.append(Paragraph("Mission & Values (excerpt)", styles["H2"]))
        elems.append(Paragraph(f"<b>Mission:</b> {mv.get('mission','')}", styles["Body"]))
        if mv.get("values"): elems.append(Paragraph("<b>Values:</b> " + ", ".join(mv.get("values")), styles["Body"]))
        if mv.get("principles"): elems.append(Paragraph("<b>Principles:</b> " + "; ".join(mv.get("principles")), styles["Body"]))

    doc.build(elems); return buf.getvalue()

# ---------- App ----------
st.set_page_config(page_title="Tracking Success", layout="wide", initial_sidebar_state="expanded")
qp = st.query_params
complete_token = qp.get("complete_task")

# Session defaults
if "business_name" not in st.session_state: st.session_state.business_name = "My Business"
if "profile" not in st.session_state:
    st.session_state.profile = {"business":{"name": st.session_state.business_name, "start_date": dt.date.today().isoformat()},
                                "functions": CORE_FUNCTIONS.copy(),
                                "roles": [{"Function": f,"Role":"","Person":"","FTE":1.0,"ReportsTo":"","KPIs":"","Accountabilities":"","Notes":""} for f in CORE_FUNCTIONS],
                                "years": {},
                                "integrations": {}}
if "current_logo_path" not in st.session_state: st.session_state.current_logo_path = storage_load_logo_path(st.session_state.business_name)
if "selected_year" not in st.session_state: st.session_state.selected_year = CUR_YEAR

# Sidebar — Admin
with st.sidebar:
    with st.expander("Admin", expanded=False):
        profiles = storage_list_profiles()
        sel = st.selectbox("Open business profile", ["(none)"]+profiles, index=0)
        if st.button("Open"):
            if sel!="(none)":
                data = storage_read_profile(sel)
                if data:
                    st.session_state.profile = data
                    st.session_state.business_name = data.get("business",{}).get("name", sel)
                    st.session_state.current_logo_path = storage_load_logo_path(st.session_state.business_name)
                    years = list((data.get("years") or {}).keys())
                    if years: st.session_state.selected_year = int(years[0])
                    st.success(f"Loaded: {sel}"); st.rerun()
                else:
                    st.error("Failed to open profile.")
        st.markdown("---")
        st.text_input("New business name", value=st.session_state.profile["business"]["name"], key="sb_new_name")
        st.date_input("Account start date", value=dt.date.fromisoformat(st.session_state.profile["business"].get("start_date", dt.date.today().isoformat())), key="sb_start_date")
        logo = st.file_uploader("Upload/Change logo", type=["png","jpg","jpeg","svg"])
        if st.button("Attach Logo"):
            tgt = st.session_state.sb_new_name.strip() or st.session_state.business_name
            if logo is None: st.warning("Choose a logo file first.")
            else:
                path = storage_save_logo(tgt, logo)
                if path:
                    st.session_state.profile["business"]["name"] = tgt
                    st.session_state.profile["business"]["start_date"] = st.session_state.sb_start_date.isoformat()
                    st.session_state.business_name = tgt
                    st.session_state.current_logo_path = path
                    storage_write_profile(tgt, st.session_state.profile)
                    st.success("Logo attached and profile saved."); st.rerun()
        c1,c2 = st.columns(2)
        with c1:
            if st.button("Save"):
                nm = st.session_state.sb_new_name.strip() or "My Business"
                st.session_state.profile["business"]["name"] = nm
                st.session_state.profile["business"]["start_date"] = st.session_state.sb_start_date.isoformat()
                ok = storage_write_profile(nm, st.session_state.profile)
                st.success("Saved.") if ok else st.error("Save failed."); st.rerun()
        with c2:
            new_as = st.text_input("Save As…", key="sb_saveas", placeholder="New business name")
            if st.button("Save As"):
                nm = new_as.strip() or st.session_state.sb_new_name.strip() or "My Business"
                st.session_state.profile["business"]["name"] = nm
                st.session_state.profile["business"]["start_date"] = st.session_state.sb_start_date.isoformat()
                ok = storage_write_profile(nm, st.session_state.profile)
                if ok: st.session_state.business_name = nm; st.success(f"Saved as {nm}"); st.rerun()
                else: st.error("Save As failed.")
        with st.popover("Delete selected business"):
            st.caption("This permanently deletes the selected profile and its logo(s).")
            confirm = st.checkbox("I understand", key="chk_del")
            if st.button("Delete") and confirm:
                if sel=="(none)":
                    st.warning("Select a profile to delete.")
                else:
                    try: os.remove(os.path.join(PROFILES_DIR, f"{_slug(sel)}.json"))
                    except FileNotFoundError: pass
                    for ext in (".png",".jpg",".jpeg",".svg"):
                        p=os.path.join(LOGOS_DIR, f"{_slug(sel)}{ext}")
                        try: os.remove(p)
                        except FileNotFoundError: pass
                    st.success(f"Deleted: {sel}"); st.rerun()

    with st.expander("Integrations (Push Sync)", expanded=False):
        integ = st.session_state.profile.get("integrations", {})
        upcoach_url = st.text_input("UpCoach Webhook URL", value=integ.get("upcoach_url",""))
        app_base_url = st.text_input("App Base URL (for completion links)", value=integ.get("app_base_url",""))
        calendly_url = st.text_input("Calendly link (optional)", value=integ.get("calendly_url",""))
        email_from   = st.text_input("SMTP From (email)", value=integ.get("smtp_from",""))
        smtp_host    = st.text_input("SMTP Host", value=integ.get("smtp_host",""))
        smtp_port    = st.number_input("SMTP Port", value=int(integ.get("smtp_port",587)), step=1, min_value=1)
        smtp_user    = st.text_input("SMTP Username", value=integ.get("smtp_user",""))
        smtp_pass    = st.text_input("SMTP Password", type="password", value=integ.get("smtp_pass",""))
        c1,c2,c3 = st.columns(3)
        with c1:
            if st.button("Save Integration Settings"):
                integ.update({"upcoach_url":upcoach_url,"app_base_url":app_base_url,"calendly_url":calendly_url,
                              "smtp_from":email_from,"smtp_host":smtp_host,"smtp_port":int(smtp_port),
                              "smtp_user":smtp_user,"smtp_pass":smtp_pass})
                st.session_state.profile["integrations"]=integ
                storage_write_profile(st.session_state.business_name, st.session_state.profile)
                st.success("Saved integration settings.")
        with c2:
            if st.button("Send Test Webhook"):
                if not requests or not upcoach_url.strip():
                    st.warning("Need requests and UpCoach URL")
                else:
                    try:
                        r = requests.post(upcoach_url, json={"event":"test","business":st.session_state.business_name,"ts":dt.datetime.utcnow().isoformat()}, timeout=8)
                        st.success(f"Webhook status {r.status_code}")
                    except Exception as e:
                        st.error(f"Webhook failed: {e}")
        with c3:
            if st.button("Send Test Email"):
                if not smtplib:
                    st.error("SMTP not available on server.")
                elif not (smtp_host and email_from and smtp_user and smtp_pass):
                    st.warning("Fill SMTP settings first.")
                else:
                    try:
                        msg=MIMEMultipart("alternative")
                        msg["Subject"]="Tracking Success — Test Email"
                        msg["From"]=email_from; msg["To"]=email_from
                        html="<p>This is a test email from Tracking Success.</p>"
                        msg.attach(MIMEText(html,"html"))
                        with smtplib.SMTP(smtp_host, int(smtp_port)) as s:
                            s.starttls(); s.login(smtp_user, smtp_pass); s.sendmail(email_from, [email_from], msg.as_string())
                        st.success("Test email sent.")
                    except Exception as e:
                        st.error(f"Email failed: {e}")

# Header
c0, c1 = st.columns([1,3])
with c0:
    if st.session_state.current_logo_path and os.path.exists(st.session_state.current_logo_path):
        st.image(st.session_state.current_logo_path, use_container_width=True)
with c1:
    st.title("Tracking Success")
    st.caption("Profiles • Streams • Organisation • People • Tracking • PDFs • Tasks • Push Sync • Journey • Values • Trade Calculator")

# Ensure year
profile = st.session_state.profile
ensure_year(profile, st.session_state.selected_year)
yk = str(st.session_state.selected_year)
yb = profile["years"][yk]

# One-click task completion via URL token
if complete_token:
    for t in yb.get("tasks", []):
        if t.get("token")==complete_token:
            t["status"]="Done"
            st.success(f"Task '{t.get('title','')}' marked complete via link.")
            integ = profile.get("integrations", {})
            if integ.get("upcoach_url") and requests:
                try: requests.post(integ["upcoach_url"], json={"event":"task.completed","business":profile['business']['name'],"task":t}, timeout=8)
                except Exception: pass
            break

# --- Organisation: Functions & Roles ---
with st.expander("Organisation: Functions & Roles", expanded=False):
    st.write("Define your functions and map roles/people (this drives costs & reporting).")
    funcs = profile.get("functions", CORE_FUNCTIONS.copy())
    new_fn = st.text_input("Add a function", key="fn_add")
    cA,cB = st.columns(2)
    with cA:
        if st.button("➕ Add Function"):
            if new_fn.strip() and new_fn not in funcs:
                funcs.append(new_fn.strip()); profile["functions"]=funcs
    with cB:
        if st.button("Reset to Core"):
            profile["functions"]=CORE_FUNCTIONS.copy(); funcs=profile["functions"]
    st.caption("Current: " + ", ".join(funcs))

    df = pd.DataFrame(profile.get("roles", []), columns=ROLE_COLUMNS)
    edited = st.data_editor(
        df, num_rows="dynamic", use_container_width=True, hide_index=True,
        column_config={
            "Function": st.column_config.SelectboxColumn(options=funcs, required=True),
            "FTE": st.column_config.NumberColumn(min_value=0.0, max_value=1.0, step=0.1, format="%.1f"),
            "KPIs": st.column_config.TextColumn(help="Comma-separated"),
            "Accountabilities": st.column_config.TextColumn(help="Bullets or lines"),
        })
    profile["roles"]=edited.fillna("").to_dict(orient="records")

# --- Revenue Streams ---
with st.expander("Revenue Streams (this year)", expanded=False):
    rev = pd.DataFrame(yb.get("revenue_streams", default_streams()), columns=REVENUE_COLUMNS)
    rev["TargetValue"]=pd.to_numeric(rev["TargetValue"], errors="coerce").fillna(0.0)
    edited = st.data_editor(rev, num_rows="dynamic", use_container_width=True, hide_index=True,
                            column_config={
                                "Stream": st.column_config.TextColumn(),
                                "TargetValue": st.column_config.NumberColumn(format="%.0f"),
                                "Notes": st.column_config.TextColumn(),
                            })
    yb["revenue_streams"]=edited.fillna("").to_dict(orient="records")
    streams_total = float(edited["TargetValue"].sum())
    lock_goal = bool(yb.get("lock_goal", True))
    st.metric("Total Streams", f"${streams_total:,.0f}")
    if lock_goal:
        yb["revenue_goal"]=streams_total
    else:
        yb["revenue_goal"]=st.number_input("Revenue Goal (override)", min_value=0.0, value=float(yb.get("revenue_goal", streams_total)), step=1000.0)

# --- People Costs & Vans ---
with st.expander("People Costs (Annual) & Vans", expanded=False):
    st.number_input("Default van monthly cost ($)", min_value=0.0, value=float(yb.get("van_monthly_default",1200.0)), step=50.0, key="van_default")
    yb["van_monthly_default"]=float(st.session_state.van_default)
    # ensure people list from roles people
    role_people = sorted({(r.get("Person") or "").strip() for r in profile.get("roles", []) if (r.get("Person") or "").strip()})
    pc = pd.DataFrame(yb.get("people_costs", []))
    if pc.empty and role_people:
        pc = pd.DataFrame([{"Person":p,"AnnualCost":0.0,"StartMonth":1,"HasVan":False,"Comment":"","ExtraMonthly":0.0} for p in role_people])
    colmap = ["Person","AnnualCost","StartMonth","HasVan","Comment","ExtraMonthly"]
    for c in colmap:
        if c not in pc.columns: pc[c]=0 if c!="Person" and c!="Comment" and c!="HasVan" else ("" if c in ("Person","Comment") else False)
    pc["AnnualCost"]=pd.to_numeric(pc["AnnualCost"], errors="coerce").fillna(0.0)
    pc["StartMonth"]=pd.to_numeric(pc["StartMonth"], errors="coerce").fillna(1).clip(1,12).astype(int)
    pc["ExtraMonthly"]=pd.to_numeric(pc["ExtraMonthly"], errors="coerce").fillna(0.0)
    edited = st.data_editor(pc[colmap], num_rows="dynamic", use_container_width=True, hide_index=True,
                            column_config={
                                "Person": st.column_config.TextColumn(),
                                "AnnualCost": st.column_config.NumberColumn(format="%.0f"),
                                "StartMonth": st.column_config.NumberColumn(min_value=1, max_value=12, step=1),
                                "HasVan": st.column_config.CheckboxColumn(),
                                "Comment": st.column_config.TextColumn(help="e.g., Trade with van, Apprentice"),
                                "ExtraMonthly": st.column_config.NumberColumn(format="%.0f", help="Van or extras per month"),
                            })
    yb["people_costs"]=edited.fillna({"Comment":""}).to_dict(orient="records")

# --- Setup: Account start date & Horizon goals & Data sources ---
with st.expander("Setup — Timing & Goals & Data sources (per company)", expanded=False):
    st.date_input("Account Start Date", value=dt.date.fromisoformat(yb.get("account_start_date", profile["business"].get("start_date", dt.date.today().isoformat()))), key="acc_start_date")
    yb["account_start_date"]=st.session_state.acc_start_date.isoformat()
    c1,c2,c3,c4 = st.columns(4)
    yb["horizon_goals"]["M1"] = c1.number_input("1‑month goal ($)", min_value=0.0, value=float(yb["horizon_goals"].get("M1") or 0.0), step=1000.0)
    yb["horizon_goals"]["M3"] = c2.number_input("3‑month goal ($)", min_value=0.0, value=float(yb["horizon_goals"].get("M3") or 0.0), step=1000.0)
    yb["horizon_goals"]["M6"] = c3.number_input("6‑month goal ($)", min_value=0.0, value=float(yb["horizon_goals"].get("M6") or 0.0), step=1000.0)
    yb["horizon_goals"]["M12"]= c4.number_input("12‑month goal ($)",min_value=0.0, value=float(yb["horizon_goals"].get("M12") or 0.0), step=1000.0)
    st.markdown("**Per‑company data sources** (name + URL)")
    ds = yb.get("data_sources", [])
    if not isinstance(ds,list): ds=[]
    # render simple editor
    ed = pd.DataFrame(ds) if ds else pd.DataFrame([{"name":"Website","url":"https://"}])
    ed = st.data_editor(ed, num_rows="dynamic", use_container_width=True, hide_index=True,
                        column_config={"name": st.column_config.TextColumn(), "url": st.column_config.LinkColumn()})
    yb["data_sources"]=ed.fillna("").to_dict(orient="records")

# --- Tracking Quick Entry ---
with st.expander("Tracking — Quick Entry", expanded=False):
    months_seq = months_from_start(yb.get("account_start_date", profile["business"].get("start_date", dt.date.today().isoformat())))
    month = st.selectbox("Month", options=months_seq, index=0)
    rev = st.number_input("Revenue (this month)", min_value=0.0, value=0.0, step=100.0)
    cos = st.number_input("Cost of Sales (materials etc)", min_value=0.0, value=0.0, step=100.0)
    oth = st.number_input("Other Overheads (rent, admin, etc)", min_value=0.0, value=0.0, step=100.0)
    if st.button("Save Month Entry"):
        ma = pd.DataFrame(yb.get("monthly_actuals", default_monthly_actuals(yb.get("account_start_date", profile["business"].get("start_date", dt.date.today().isoformat())))))
        if month in list(ma["Month"]):
            idx = list(ma["Month"]).index(month)
            ma.loc[idx,"RevenueActual"]=rev; ma.loc[idx,"CostOfSales"]=cos; ma.loc[idx,"OtherOverheads"]=oth
            yb["monthly_actuals"]=ma.to_dict(orient="records")
            st.success(f"Saved {month}.")

# --- Coaching Notes & Assets ---
with st.expander("Coaching — Notes, Screenshots & URLs", expanded=False):
    ns = yb.get("coaching_assets", {})
    msel = st.selectbox("Month", options=MONTHS, index=0)
    notes = st.text_area("Notes (context for the month)", value=(ns.get(msel,{}).get("notes","")))
    # URLs
    st.markdown("**Links / URLs**")
    link_url = st.text_input("Add a URL", placeholder="https://...")
    link_caption = st.text_input("Caption")
    add_link = st.button("Add link")
    if add_link and link_url.strip():
        pack = ns.get(msel, {"images":[], "links":[], "notes":""})
        pack["links"].append({"url":link_url.strip(),"caption":link_caption.strip(),"include":True})
        ns[msel]=pack
    # Images
    st.markdown("**Screenshots**")
    imgs = st.file_uploader("Upload screenshot(s)", type=["png","jpg","jpeg"], accept_multiple_files=True)
    if st.button("Upload screenshot(s)") and imgs:
        pack = ns.get(msel, {"images":[], "links":[], "notes":""})
        for f in imgs:
            ext=os.path.splitext(f.name)[1].lower() or ".png"
            dst=os.path.join(ASSETS_DIR, f"{uuid.uuid4().hex}{ext}")
            open(dst,"wb").write(f.read())
            pack["images"].append({"path":dst,"caption":f.name,"include":True})
        ns[msel]=pack
    # Included list
    pack = ns.get(msel, {"images":[], "links":[], "notes":""})
    st.write("**Included in report** — toggle as needed")
    # render checkboxes
    for i,ln in enumerate(pack.get("links", [])):
        ln["include"] = st.checkbox(f"URL: {ln.get('url','')} — {ln.get('caption','')}", value=bool(ln.get("include",True)), key=f"incl_url_{msel}_{i}")
    for i,im in enumerate(pack.get("images", [])):
        im["include"] = st.checkbox(f"Image: {im.get('caption','screenshot')}", value=bool(im.get("include",True)), key=f"incl_img_{msel}_{i}")
    pack["notes"]=notes
    ns[msel]=pack
    yb["coaching_assets"]=ns

# --- Accountability Items & Next Session ---
with st.expander("Accountability & Next Coaching Session", expanded=False):
    msel = st.selectbox("Month", options=MONTHS, index=0, key="acct_month")
    cur = yb.get("accountability", {}).get(msel, [])
    st.write("Add accountability item")
    col1,col2,col3,col4 = st.columns([3,1,1,1])
    with col1: action = st.text_input("Action", key="act_action")
    with col2: owner  = st.text_input("Owner", key="act_owner")
    with col3: due    = st.text_input("Due (date)", key="act_due")
    with col4: status = st.selectbox("Status", ["Planned","In progress","Done"], index=0, key="act_status")
    notes = st.text_input("Notes", key="act_notes")
    if st.button("Add Item"):
        cur.append({"action":action,"owner":owner,"due":due,"status":status,"notes":notes})
        yb["accountability"][msel]=cur
        st.success("Added.")

    st.markdown("---")
    st.write("**Next coaching session** (FYI only — real booking lives in calendar)")
    ns = yb.get("next_session", {})
    ns["when"] = st.text_input("Agreed date/time (free text)", value=ns.get("when",""))
    ns["notes"]= st.text_input("Session notes", value=ns.get("notes",""))
    yb["next_session"]=ns

# --- Tasks with completion links ---
with st.expander("Tasks & Invitations", expanded=False):
    tasks = yb.get("tasks", [])
    c1,c2,c3,c4 = st.columns([2,1,1,1])
    with c1: t_title = st.text_input("Task title", key="tsk_t")
    with c2: t_assn  = st.text_input("Assignee (email/name)", key="tsk_a")
    with c3: t_due   = st.text_input("Due (date)", key="tsk_d")
    with c4: t_incl  = st.checkbox("Include in report", value=True, key="tsk_i")
    t_notes = st.text_input("Notes", key="tsk_n")
    if st.button("Create Task"):
        tok = uuid.uuid4().hex
        tasks.append({"id":uuid.uuid4().hex,"title":t_title,"assignee":t_assn,"due":t_due,"status":"Planned","include_in_report":t_incl,"notes":t_notes,"token":tok})
        yb["tasks"]=tasks
        # webhook: task.created
        integ = profile.get("integrations", {})
        if integ.get("upcoach_url") and requests:
            try: requests.post(integ["upcoach_url"], json={"event":"task.created","business":profile['business']['name'],"task":tasks[-1]}, timeout=8)
            except Exception: pass
        st.success("Task created.")
    st.markdown("**Current tasks**")
    app_base = profile.get("integrations",{}).get("app_base_url","")
    for t in tasks:
        link = f"{app_base}?complete_task={t.get('token')}" if app_base else "(set App Base URL to generate link)"
        st.write(f"- **{t['title']}** — {t['assignee']} — due {t['due']} — status: {t['status']} — Complete link: {link}")

# --- PUSH SYNC ---
with st.expander("PUSH SYNC", expanded=False):
    st.caption("Select destinations and push summary payload.")
    dest = st.multiselect("Destinations", ["UPCOACH","CALENDARLY","EMAIL","OTHER"])
    email_to = st.text_input("Email To (comma‑sep, if EMAIL chosen)")
    if st.button("Push now"):
        payload = {
            "event":"push.sync",
            "business": profile["business"]["name"],
            "year": int(yk),
            "summary": {
                "streams_total": sum(float(x.get("TargetValue",0.0) or 0.0) for x in yb.get("revenue_streams", [])),
                "next_session": yb.get("next_session",{}),
                "tasks": yb.get("tasks",[]),
            },
            "ts": dt.datetime.utcnow().isoformat()
        }
        integ = profile.get("integrations", {})
        log_msgs = []
        if "UPCOACH" in dest and integ.get("upcoach_url") and requests:
            try:
                r=requests.post(integ["upcoach_url"], json=payload, timeout=8)
                log_msgs.append(f"UpCoach {r.status_code}")
            except Exception as e:
                log_msgs.append(f"UpCoach failed: {e}")
        if "CALENDARLY" in dest and integ.get("calendly_url"):
            log_msgs.append(f"Calendly: {integ['calendly_url']} (share this link)")
        if "EMAIL" in dest and smtplib and integ.get("smtp_host") and integ.get("smtp_from") and integ.get("smtp_user") and integ.get("smtp_pass"):
            try:
                msg=MIMEMultipart("alternative")
                msg["Subject"]=f"Tracking Success — {profile['business']['name']} — Sync"
                msg["From"]=integ["smtp_from"]; tos=[e.strip() for e in email_to.split(",") if e.strip()]
                msg["To"]=",".join(tos or [integ["smtp_from"]])
                html=f"<p>Sync payload:</p><pre>{json.dumps(payload, indent=2)}</pre>"
                msg.attach(MIMEText(html,"html"))
                with smtplib.SMTP(integ["smtp_host"], int(integ["smtp_port"])) as s:
                    s.starttls(); s.login(integ["smtp_user"], integ["smtp_pass"]); s.sendmail(integ["smtp_from"], tos or [integ["smtp_from"]], msg.as_string())
                log_msgs.append("Email sent")
            except Exception as e:
                log_msgs.append(f"Email failed: {e}")
        if "OTHER" in dest:
            log_msgs.append("Other: (no‑op stub)")
        st.success(" ; ".join(log_msgs) if log_msgs else "Nothing to push: configure integrations.")

# --- Mission & Values ---
with st.expander("Mission & Values (foundations)", expanded=False):
    mv = yb.get("mission_values", {"mission":"","values":[],"principles":[],"trust_model":"Earned","prompts":{}})
    st.write("Use this to define how you genuinely operate — not buzzwords.")
    mv["mission"] = st.text_area("Mission (plain English)",
                                 value=mv.get("mission",""),
                                 placeholder="Why you exist; who you serve; what great looks like.")
    mv["trust_model"] = st.selectbox("Trust model", ["Default trust (trust first)","Earned trust (verify then trust)"],
                                     index=1 if mv.get("trust_model","Earned").startswith("Earned") else 0)
    values_str = st.text_input("Values (comma‑separated)", value=", ".join(mv.get("values",[])))
    mv["values"] = [v.strip() for v in values_str.split(",") if v.strip()]
    principles_str = st.text_area("Principles / behaviours (one per line)", value="\n".join(mv.get("principles",[])))
    mv["principles"] = [p.strip() for p in principles_str.splitlines() if p.strip()]
    st.caption("Prompts (optional reflections)")
    p1 = st.text_area("Owner lens — how do you want people to experience working with you?",
                      value=mv.get("prompts",{}).get("owner_lens",""))
    p2 = st.text_area("Trust notes — when do you delegate vs verify?",
                      value=mv.get("prompts",{}).get("trust_notes",""))
    mv["prompts"]={"owner_lens":p1,"trust_notes":p2}
    yb["mission_values"]=mv

# --- Customer Journey Mapping (beta) ---
with st.expander("Customer Journey Mapping (beta)", expanded=False):
    def_j_cols = ["Actions","Touchpoints","Emotions","PainPoints","Solutions"]
    journey = profile.get("journey", {"stages":["Awareness","Consideration","Purchase","Service","Loyalty"], "columns":def_j_cols, "data":{}})
    stages = journey.get("stages",[])
    cols   = journey.get("columns",def_j_cols)
    data   = journey.get("data", {s:[{c:""} for c in cols] for s in stages} if stages else {})
    cA,cB = st.columns([3,1])
    with cA: new_stage=st.text_input("Add stage")
    with cB:
        if st.button("➕ Add stage") and new_stage.strip():
            if new_stage not in stages:
                stages.append(new_stage.strip()); data[new_stage.strip()]=[{c:""} for c in cols]
    del_sel = st.selectbox("Delete stage", ["(none)"]+stages)
    if st.button("🗑️ Delete") and del_sel!="(none)":
        stages.remove(del_sel); data.pop(del_sel,None)
    st.markdown("---")
    for s in stages:
        st.subheader(s)
        df = pd.DataFrame(data.get(s, []), columns=cols)
        edited = st.data_editor(df, num_rows="dynamic", use_container_width=True, hide_index=True)
        data[s]=edited.fillna("").to_dict(orient="records")
    journey["stages"]=stages; journey["columns"]=cols; journey["data"]=data
    profile["journey"]=journey

# --- Dashboard & Reports ---
st.header("Dashboard & Reports")
df_dash = build_dashboard_df(yb)
c1,c2,c3 = st.columns(3)
with c1: st.metric("Revenue goal (12‑mo)", f"${float(yb.get('revenue_goal',0.0)):,.0f}")
with c2: st.metric("YTD Revenue", f"${float(df_dash['RevenueActual'].sum()):,.0f}")
with c3: st.metric("YTD Operating Profit", f"${float(df_dash['OperatingProfit'].sum()):,.0f}")

# Charts
fig1, ax = plt.subplots(figsize=(8,3))
x=list(range(len(df_dash)))
ax.plot(x, df_dash["PlannedRevenue"], marker="")
ax.plot(x, df_dash["RevenueActual"], marker="")
ax.plot(x, df_dash["BreakEvenRevenue"], marker="")
ax.set_xticks(x); ax.set_xticklabels(df_dash["Month"], rotation=45, ha="right")
ax.set_ylabel("Revenue ($)"); ax.legend(["Planned","Actual","Break‑even"])
st.pyplot(fig1)

fig2, ax1 = plt.subplots(figsize=(8,3))
ax1.bar(x, df_dash["OperatingProfit"].fillna(0.0))
ax1.set_xticks(x); ax1.set_xticklabels(df_dash["Month"], rotation=45, ha="right")
ax1.set_ylabel("Operating Profit ($)")
ax2=ax1.twinx(); ax2.plot(x, [m if m is not None else float('nan') for m in df_dash["MarginPct"]], marker="o")
ax2.set_ylabel("Margin %")
st.pyplot(fig2)

# Report buttons
colA,colB = st.columns(2)
with colA:
    if st.button("Download Tracking PDF"):
        pdf_bytes = build_tracking_pdf(profile, int(yk), df_dash, st.session_state.current_logo_path,
                                       yb.get("accountability",{}), yb.get("next_session",{}),
                                       yb.get("coaching_assets",{}), yb.get("tasks",[]))
        st.download_button("Save Tracking.pdf", data=pdf_bytes, file_name=f"Tracking_{profile['business']['name']}_{yk}.pdf", mime="application/pdf")
with colB:
    st.write("Details PDF — include sections:")
    inc_streams = st.checkbox("Revenue Streams", value=True)
    inc_roles   = st.checkbox("Organisation / Roles", value=True)
    inc_people  = st.checkbox("People Costs", value=True)
    inc_monthly = st.checkbox("Monthly Plan & Actuals", value=True)
    if st.button("Download Details PDF"):
        pdf2=build_details_pdf(profile, int(yk), {"streams":inc_streams,"roles":inc_roles,"people":inc_people,"monthly":inc_monthly}, st.session_state.current_logo_path)
        st.download_button("Save Details.pdf", data=pdf2, file_name=f"Details_{profile['business']['name']}_{yk}.pdf", mime="application/pdf")

# --- Trade Profit Calculator ---
with st.expander("Trade Profit Calculator (beta)", expanded=False):
    st.caption("Estimate blended rate to hit profit target based on team, utilisation, quotes→jobs, materials %, marketing, and overheads.")
    weeks = st.number_input("Weeks in period", min_value=1.0, value=4.33, step=0.25)
    mat_pct = st.number_input("Materials (COGS) % of revenue", min_value=0.0, max_value=95.0, value=25.0, step=1.0)
    current_rate = st.number_input("Your current blended rate ($/hr)", min_value=0.0, value=120.0, step=5.0)
    st.subheader("Team")
    team = pd.DataFrame([
        {"Person":"Tradie 1","Role":"Tradie","HourlyWageCost":40.0,"VanMonthly":1200.0,"PaidHoursPerWeek":38.0,"UtilisationPct":70.0,"QuotesPerWeek":3.0,"QuoteToJobPct":40.0,"AvgJobHours":2.0},
        {"Person":"Apprentice 1","Role":"Apprentice","HourlyWageCost":25.0,"VanMonthly":0.0,"PaidHoursPerWeek":38.0,"UtilisationPct":65.0,"QuotesPerWeek":1.0,"QuoteToJobPct":35.0,"AvgJobHours":1.5},
    ])
    team = st.data_editor(team, num_rows="dynamic", use_container_width=True, hide_index=True)
    team = team.fillna(0.0)
    col1,col2 = st.columns(2)
    with col1: mkt = st.number_input("Marketing ($/month)", min_value=0.0, value=2000.0, step=100.0)
    with col2: oth = st.number_input("Other overheads ($/month)", min_value=0.0, value=8000.0, step=100.0)
    t1,t2,t3 = st.columns(3)
    with t1: hours_source = st.selectbox("Use hours from", ["Capacity (utilisation)","Demand (quotes→jobs)"])
    with t2: target_mode = st.selectbox("Target type", ["Profit $","Profit Margin %"])
    with t3: target_profit = st.number_input("Target profit ($)", min_value=0.0, value=10000.0, step=500.0)
    margin_pct = st.slider("Target margin % (if using margin)", min_value=0, max_value=70, value=20, step=1)

    team["PaidHoursPeriod"] = team["PaidHoursPerWeek"] * weeks
    team["BillableHoursPeriod"] = team["PaidHoursPeriod"] * (team["UtilisationPct"]/100.0)
    team["JobsFromQuotes"] = (team["QuotesPerWeek"] * weeks) * (team["QuoteToJobPct"]/100.0)
    team["BillableFromJobs"] = team["JobsFromQuotes"] * team["AvgJobHours"]
    H = float(team["BillableHoursPeriod"].sum()) if hours_source.startswith("Capacity") else float(team["BillableFromJobs"].sum())

    team["WageCostPeriod"] = team["HourlyWageCost"] * team["PaidHoursPeriod"]
    team["VanCostPeriod"]  = team["VanMonthly"] * (weeks/4.33)
    people_costs = float((team["WageCostPeriod"] + team["VanCostPeriod"]).sum())
    mkt_p = mkt * (weeks/4.33); oth_p = oth * (weeks/4.33); m = mat_pct/100.0

    if target_mode=="Profit $":
        req_rate = ((target_profit + people_costs + mkt_p + oth_p) / max(H*(1-m), 1e-6)) if H>0 else 0.0
    else:
        M = margin_pct/100.0; denom = (1 - m - M)
        req_rate = ((people_costs + mkt_p + oth_p) / max(H*denom, 1e-6)) if H>0 else 0.0

    revenue_at_current = current_rate * H
    profit_at_current  = revenue_at_current - (m*revenue_at_current) - people_costs - mkt_p - oth_p
    margin_at_current  = (profit_at_current/revenue_at_current*100.0) if revenue_at_current>0 else 0.0

    s1,s2,s3 = st.columns(3)
    with s1: st.metric("Billable hours (period)", f"{H:,.1f}")
    with s2: st.metric("Required blended rate", f"${req_rate:,.2f}/hr")
    with s3: st.metric("At current rate", f"Profit ${profit_at_current:,.0f} ({margin_at_current:,.1f}%)")

    st.subheader("Per‑person contribution (at required rate)")
    share = team[["Person","BillableHoursPeriod" if hours_source.startswith("Capacity") else "BillableFromJobs"]].copy()
    share = share.rename(columns={"BillableHoursPeriod":"BillableHrs","BillableFromJobs":"BillableHrs"})
    share["RevenueAtRequired"] = req_rate * share["BillableHrs"]
    share["WageCostPeriod"] = team["WageCostPeriod"]
    share["VanCostPeriod"]  = team["VanCostPeriod"]
    tot_rev = float(share["RevenueAtRequired"].sum())
    if tot_rev>0:
        share["COGS"] = m * share["RevenueAtRequired"]
        share["OverheadsAlloc"] = (mkt_p + oth_p) * (share["RevenueAtRequired"]/tot_rev)
    else:
        share["COGS"]=0.0; share["OverheadsAlloc"]=0.0
    share["Profit"] = share["RevenueAtRequired"] - share["COGS"] - share["WageCostPeriod"] - share["VanCostPeriod"] - share["OverheadsAlloc"]
    st.dataframe(share, use_container_width=True)

# Persist profile on every interaction
storage_write_profile(st.session_state.business_name, profile)
