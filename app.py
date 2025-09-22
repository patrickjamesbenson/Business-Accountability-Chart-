# app.py — Success Dynamics Accountability Coach — v7.1 (duplicate widget IDs fixed)
from __future__ import annotations

import os, json, re, calendar, tempfile, datetime as dt
from io import BytesIO
from typing import Optional, List, Dict, Any

import pandas as pd
import streamlit as st

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak

try:
    import boto3
    from botocore.exceptions import ClientError
except Exception:
    boto3 = None
    ClientError = Exception

CORE_FUNCTIONS = ["Sales & Marketing", "Operations", "Finance"]
ROLE_COLUMNS = ["Function","Role","Person","FTE","ReportsTo","KPIs","Accountabilities","Notes"]
REVENUE_COLUMNS = ["Stream","TargetValue","Notes"]
MONTHS = list(calendar.month_name)[1:]
CUR_YEAR = dt.datetime.now().year

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
PROFILES_DIR = os.path.join(APP_ROOT, "data", "profiles")
LOGOS_DIR    = os.path.join(APP_ROOT, "data", "logos")
os.makedirs(PROFILES_DIR, exist_ok=True)
os.makedirs(LOGOS_DIR, exist_ok=True)
for d in (PROFILES_DIR, LOGOS_DIR):
    keep = os.path.join(d, ".gitkeep")
    if not os.path.exists(keep): open(keep,"w").close()

def _slugify(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+","_", (name or "business")).strip("_") or "business"

def _storage_mode() -> str:
    return os.getenv("SD_STORAGE", "local").lower()

def _s3_client():
    if boto3 is None: return None
    return boto3.client("s3")

def _s3_bucket() -> Optional[str]:
    return os.getenv("SD_S3_BUCKET")

def _s3_prefix() -> str:
    return os.getenv("SD_S3_PREFIX", "success_dynamics")

def _profiles_prefix() -> str:
    return f"{_s3_prefix().rstrip('/')}/profiles/"

def _logos_prefix() -> str:
    return f"{_s3_prefix().rstrip('/')}/logos/"

def storage_list_profiles() -> list[str]:
    if _storage_mode()=="s3" and _s3_bucket() and _s3_client():
        s3 = _s3_client(); bucket = _s3_bucket()
        names=set()
        try:
            paginator = s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket, Prefix=_profiles_prefix()):
                for obj in page.get("Contents", []):
                    if obj["Key"].endswith(".json"):
                        names.add(os.path.splitext(os.path.basename(obj["Key"]))[0])
            return sorted(names)
        except ClientError:
            return []
    return sorted([os.path.splitext(fn)[0] for fn in os.listdir(PROFILES_DIR) if fn.lower().endswith(".json")])

def storage_read_profile(name: str) -> Optional[dict]:
    if _storage_mode()=="s3" and _s3_bucket() and _s3_client():
        s3=_s3_client(); bucket=_s3_bucket(); key=_profiles_prefix()+f"{_slugify(name)}.json"
        try:
            obj=s3.get_object(Bucket=bucket, Key=key)
            return json.loads(obj["Body"].read().decode("utf-8"))
        except ClientError:
            return None
    path=os.path.join(PROFILES_DIR, f"{_slugify(name)}.json")
    if os.path.exists(path):
        return json.loads(open(path,"r",encoding="utf-8").read())
    return None

def storage_write_profile(name: str, data: dict) -> bool:
    payload=json.dumps(data, indent=2).encode("utf-8")
    if _storage_mode()=="s3" and _s3_bucket() and _s3_client():
        s3=_s3_client(); bucket=_s3_bucket(); key=_profiles_prefix()+f"{_slugify(name)}.json"
        try:
            s3.put_object(Bucket=bucket, Key=key, Body=payload, ContentType="application/json")
            return True
        except ClientError:
            return False
    path=os.path.join(PROFILES_DIR, f"{_slugify(name)}.json")
    try:
        with open(path,"wb") as f: f.write(payload)
        return True
    except Exception:
        return False

def storage_delete_profile(name: str) -> bool:
    ok=True
    if _storage_mode()=="s3" and _s3_bucket() and _s3_client():
        s3=_s3_client(); bucket=_s3_bucket()
        key=_profiles_prefix()+f"{_slugify(name)}.json"
        try: s3.delete_object(Bucket=bucket, Key=key)
        except ClientError: ok=False
        base=_slugify(name)
        for ext in (".png",".jpg",".jpeg",".svg"):
            try: s3.delete_object(Bucket=bucket, Key=_logos_prefix()+f"{base}{ext}")
            except ClientError: pass
        return ok
    try: os.remove(os.path.join(PROFILES_DIR, f"{_slugify(name)}.json"))
    except FileNotFoundError: pass
    base=_slugify(name)
    for ext in (".png",".jpg",".jpeg",".svg"):
        p=os.path.join(LOGOS_DIR, f"{base}{ext}")
        try: os.remove(p)
        except FileNotFoundError: pass
    return ok

def storage_save_logo(name: str, file) -> Optional[str]:
    if file is None: return None
    fname=getattr(file,"name","logo.png"); _,ext=os.path.splitext(fname.lower())
    if ext not in [".png",".jpg",".jpeg",".svg"]: ext=".png"
    base=_slugify(name)
    if _storage_mode()=="s3" and _s3_bucket() and _s3_client():
        s3=_s3_client(); bucket=_s3_bucket()
        for e in (".png",".jpg",".jpeg",".svg"):
            try: s3.delete_object(Bucket=bucket, Key=_logos_prefix()+f"{base}{e}")
            except ClientError: pass
        key=_logos_prefix()+f"{base}{ext}"
        data=file.read()
        try: s3.put_object(Bucket=bucket, Key=key, Body=data, ContentType="image/"+ext.strip("."))
        except ClientError: return None
        tmp=os.path.join(tempfile.gettempdir(), f"{base}{ext}")
        with open(tmp,"wb") as f: f.write(data)
        return tmp
    for e in (".png",".jpg",".jpeg",".svg"):
        p=os.path.join(LOGOS_DIR, f"{base}{e}")
        try: os.remove(p)
        except FileNotFoundError: pass
    dst=os.path.join(LOGOS_DIR, f"{base}{ext}")
    with open(dst,"wb") as f: f.write(file.read())
    return dst

def storage_load_logo_path(name: str) -> Optional[str]:
    base=_slugify(name)
    if _storage_mode()=="s3" and _s3_bucket() and _s3_client():
        s3=_s3_client(); bucket=_s3_bucket()
        for ext in (".png",".jpg",".jpeg",".svg"):
            key=_logos_prefix()+f"{base}{ext}"
            try:
                s3.head_object(Bucket=bucket, Key=key)
                tmp=os.path.join(tempfile.gettempdir(), f"{base}{ext}")
                s3.download_file(bucket, key, tmp)
                return tmp
            except ClientError:
                continue
        return None
    for ext in (".png",".jpg",".jpeg",".svg"):
        p=os.path.join(LOGOS_DIR, f"{base}{ext}")
        if os.path.exists(p): return p
    return None

def default_streams():
    return [
        {"Stream":"New Clients","TargetValue":400000,"Notes":""},
        {"Stream":"Subscriptions / Recurring","TargetValue":300000,"Notes":""},
        {"Stream":"Upsell (New Program)","TargetValue":250000,"Notes":""},
        {"Stream":"Other / Experiments","TargetValue":50000,"Notes":""},
    ]

def default_people_costs(persons: list[str]) -> pd.DataFrame:
    return pd.DataFrame([{"Person": p, "AnnualCost": 0.0, "StartMonth": 1, "Comment":"", "ExtraMonthly": 0.0} for p in persons],
                        columns=["Person","AnnualCost","StartMonth","Comment","ExtraMonthly"])

def default_monthly_plan(goal: float) -> pd.DataFrame:
    per=(goal or 0.0)/12.0
    return pd.DataFrame({"Month": MONTHS, "PlannedRevenue": [per]*12})

def default_monthly_actuals() -> pd.DataFrame:
    return pd.DataFrame({"Month": MONTHS, "RevenueActual":[0.0]*12, "CostOfSales":[0.0]*12, "OtherOverheads":[0.0]*12})

def default_accountability() -> dict:
    return {m: [] for m in MONTHS}

def default_next_session() -> dict:
    return {}

def ensure_year_block(profile: dict, year: int, revenue_goal: float) -> dict:
    years=profile.setdefault("years",{}); key=str(year)
    if key not in years:
        years[key]={
            "lock_goal": True,
            "revenue_goal": float(revenue_goal),
            "revenue_streams": default_streams(),
            "people_costs": [],
            "monthly_plan": default_monthly_plan(revenue_goal).to_dict(orient="records"),
            "monthly_actuals": default_monthly_actuals().to_dict(orient="records"),
            "accountability": default_accountability(),
            "next_session": default_next_session(),
            "account_start_date": None,
            "horizon_goals": {"M1": None, "M3": None, "M6": None, "M12": None},
            "van_monthly_default": 1200.0,
        }
    return profile

def rotate_months_from(start_month_idx: int) -> list[str]:
    idx=(start_month_idx-1)%12
    return MONTHS[idx:]+MONTHS[:idx]

def fig_to_buf(fig) -> bytes:
    out=BytesIO(); fig.savefig(out, format="png", bbox_inches="tight", dpi=160); plt.close(fig); return out.getvalue()

def build_tracking_pdf(profile: dict, year: int, df_dash: pd.DataFrame, logo_path: Optional[str],
                       accountability: dict, next_session: dict) -> bytes:
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

    elems.append(PageBreak())
    elems.append(Paragraph("Accountability (by month)", styles["H2"]))
    rows=[["Month","Action","Owner","Due","Status","Notes"]]
    for m in MONTHS:
        for it in accountability.get(m, []):
            rows.append([m,it.get("action",""),it.get("owner",""),it.get("due",""),it.get("status",""),it.get("notes","")])
    if len(rows)==1: rows.append(["—","—","—","—","—","—"])
    t2=Table(rows, hAlign="LEFT", colWidths=[65,200,70,55,60,130])
    t2.setStyle(TableStyle([("FONT",(0,0),(-1,-1),"Helvetica",8),("BACKGROUND",(0,0),(-1,0), colors.whitesmoke),("GRID",(0,0),(-1,-1),0.25, colors.lightgrey)]))
    elems.append(t2); elems.append(Spacer(1,6))

    elems.append(Paragraph("Next Session (by month)", styles["H2"]))
    rows3=[["Month","Date","Time","Location","Agreed note","Notes"]]
    for m in MONTHS:
        ns=next_session.get(m, {})
        rows3.append([m, ns.get("date",""), ns.get("time",""), ns.get("location",""), ns.get("agreed_note",""), ns.get("notes","")])
    t3=Table(rows3, hAlign="LEFT", colWidths=[65,70,50,90,110,150])
    t3.setStyle(TableStyle([("FONT",(0,0),(-1,-1),"Helvetica",8),("BACKGROUND",(0,0),(-1,0), colors.whitesmoke),("GRID",(0,0),(-1,-1),0.25, colors.lightgrey)]))
    elems.append(t3)

    doc.build(elems); return buf.getvalue()

def build_details_pdf(profile: dict, year: int, include_flags: dict, logo_path: Optional[str]) -> bytes:
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
    start_date = yb.get("account_start_date")
    elems.append(Paragraph(f"Revenue Goal: <b>${goal:,.0f}</b>", styles["Body"]))
    if start_date:
        elems.append(Paragraph(f"Account Start Date: <b>{start_date}</b>", styles["Body"]))
    elems.append(Spacer(1,6))

    if include_flags.get("streams"):
        elems.append(Paragraph("Revenue Streams", styles["H2"]))
        df=pd.DataFrame(yb.get("revenue_streams", []))
        if not df.empty:
            data=[["Stream","TargetValue","Notes"]]+df.fillna("").values.tolist()
            t=Table(data, hAlign="LEFT", colWidths=[220,100,160])
            t.setStyle(TableStyle([("FONT",(0,0),(-1,-1),"Helvetica",10),("BACKGROUND",(0,0),(-1,0), colors.whitesmoke),("GRID",(0,0),(-1,-1),0.25, colors.lightgrey)]))
            elems.append(t); elems.append(Spacer(1,6))

    if include_flags.get("roles"):
        elems.append(Paragraph("Roles & People", styles["H2"]))
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
            data=[["Person","AnnualCost","StartMonth","Comment","ExtraMonthly"]]+pc.fillna("").values.tolist()
            t=Table(data, hAlign="LEFT", colWidths=[150,90,70,150,90])
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

    doc.build(elems); return buf.getvalue()

def build_graphviz_dot(business_name: str, revenue_goal: float, df: pd.DataFrame) -> str:
    def _esc(s:str)->str: return (s or "").replace("\n","\\n").replace('"','\\"')
    roles=df["Role"].fillna("").astype(str).str.strip()
    people=df["Person"].fillna("").astype(str).str.strip()
    funcs=df["Function"].fillna("").astype(str).str.strip()
    grouped=df.assign(Role=roles, Person=people, Function=funcs).groupby("Function")
    dot=[
        "digraph G {",
        "  graph [rankdir=TB, splines=ortho];",
        '  node  [shape=box, style=rounded, fontname=Helvetica];',
        "  edge  [arrowhead=vee];",
        f'  root [label="{_esc(business_name)}\\n12‑month Goal: ${revenue_goal:,.0f}", shape=box, style="rounded,bold"];',
    ]
    for func,gdf in grouped:
        fid=f"cluster_{abs(hash(func))%(10**8)}"
        dot += [f"  subgraph {fid} {{",
                '    color=lightgray; style=rounded;',
                '    labeljust="l"; labelloc="t"; fontsize=12; fontname="Helvetica"; pencolor="lightgray";',
                f'    label="{_esc(func)}";']
        func_node_id=f"func_{abs(hash(func))%(10**8)}"
        dot.append(f'    {func_node_id} [label="{_esc(func)}", shape=box, style="rounded,filled", fillcolor="#f5f5f5"];')
        dot.append(f"    root -> {func_node_id};")
        for _,row in gdf.iterrows():
            role=row.get("Role","").strip(); person=row.get("Person","").strip()
            if not role: continue
            node_id=f"role_{abs(hash(role))%(10**10)}"
            label=role if not person else f"{role}\\n({person})"
            dot.append(f'    {node_id} [label="{_esc(label)}"];')
            dot.append(f"    {func_node_id} -> {node_id};")
        dot.append("  }")
    for _,row in df.iterrows():
        role=(row.get("Role","") or "").strip(); mgr=(row.get("ReportsTo","") or "").strip()
        if role and mgr:
            src=f"role_{abs(hash(mgr))%(10**10)}"; dst=f"role_{abs(hash(role))%(10**10)}"
            dot.append(f"  {src} -> {dst};")
    dot.append("}"); return "\n".join(dot)

st.set_page_config(page_title="Success Dynamics – Accountability Coach", layout="wide", initial_sidebar_state="expanded")

if "functions" not in st.session_state: st.session_state.functions=CORE_FUNCTIONS.copy()
if "roles_df" not in st.session_state: st.session_state.roles_df=pd.DataFrame([{"Function": f, "Role":"", "Person":"", "FTE":1.0, "ReportsTo":"", "KPIs":"", "Accountabilities":"", "Notes":""} for f in CORE_FUNCTIONS], columns=ROLE_COLUMNS)
if "business_name" not in st.session_state: st.session_state.business_name="My Business"
if "current_logo_path" not in st.session_state: st.session_state.current_logo_path=storage_load_logo_path(st.session_state.business_name)
if "profile" not in st.session_state:
    st.session_state.profile={"business":{"name": st.session_state.business_name},
                              "functions": st.session_state.functions,
                              "roles": st.session_state.roles_df.to_dict(orient="records"),
                              "years": {}}
if "selected_year" not in st.session_state: st.session_state.selected_year=CUR_YEAR

with st.sidebar:
    st.markdown("### Admin")
    profiles = storage_list_profiles()
    selected  = st.selectbox("Open business profile", options=["(none)"]+profiles, index=0, key="sb_open_profile")
    new_name  = st.text_input("Business name", value=st.session_state.business_name, key="sb_business_name")

    c1,c2,c3 = st.columns(3)
    with c1:
        if st.button("Open", key="btn_open"):
            if selected!="(none)":
                data=storage_read_profile(selected)
                if data:
                    st.session_state.profile=data
                    st.session_state.business_name=data.get("business",{}).get("name",selected)
                    st.session_state.functions=data.get("functions", CORE_FUNCTIONS).copy()
                    st.session_state.roles_df=pd.DataFrame(data.get("roles", []), columns=ROLE_COLUMNS) if data.get("roles") else st.session_state.roles_df
                    st.session_state.current_logo_path=storage_load_logo_path(st.session_state.business_name)
                    years=list((data.get("years") or {}).keys())
                    st.session_state.selected_year=int(years[0]) if years else CUR_YEAR
                    st.success(f"Loaded profile: {selected}"); st.rerun()
                else:
                    st.error("Failed to open profile.")
    with c2:
        if st.button("Save", key="btn_save"):
            st.session_state.business_name=new_name.strip() or "My Business"
            st.session_state.profile["business"]={"name": st.session_state.business_name}
            st.session_state.profile["functions"]=st.session_state.functions
            st.session_state.profile["roles"]=st.session_state.roles_df.fillna("").to_dict(orient="records")
            ok=storage_write_profile(st.session_state.business_name, st.session_state.profile)
            st.success("Saved.") if ok else st.error("Save failed."); st.rerun()
    with c3:
        if st.button("Save As", key="btn_save_as"):
            nm=new_name.strip() or "My Business"
            st.session_state.profile["business"]={"name": nm}
            st.session_state.profile["functions"]=st.session_state.functions
            st.session_state.profile["roles"]=st.session_state.roles_df.fillna("").to_dict(orient="records")
            ok=storage_write_profile(nm, st.session_state.profile)
            if ok: st.session_state.business_name=nm; st.success(f"Saved As: {nm}"); st.rerun()
            else: st.error("Save As failed.")

    st.markdown("---")
    st.markdown("### Danger Zone")
    confirm=st.checkbox("I understand this will permanently delete the selected profile and its logo(s).", key="chk_confirm_del")
    if st.button("Delete Profile", key="btn_delete") and confirm:
        if selected=="(none)":
            st.warning("Select a profile to delete.")
        else:
            ok=storage_delete_profile(selected)
            if ok:
                st.success(f"Deleted profile: {selected}")
                st.session_state.business_name="My Business"
                st.session_state.functions=CORE_FUNCTIONS.copy()
                st.session_state.roles_df=pd.DataFrame([{"Function": f, "Role":"", "Person":"", "FTE":1.0, "ReportsTo":"", "KPIs":"", "Accountabilities":"", "Notes":""} for f in CORE_FUNCTIONS], columns=ROLE_COLUMNS)
                st.session_state.profile={"business":{"name":"My Business"}, "functions":st.session_state.functions, "roles":st.session_state.roles_df.to_dict(orient="records"), "years":{}}
                st.session_state.selected_year=CUR_YEAR
                st.session_state.current_logo_path=None
                st.rerun()
            else:
                st.error("Delete failed.")

    st.markdown("---")
    st.markdown("### Branding")
    logo_file=st.file_uploader("Upload/Change logo", type=["png","jpg","jpeg","svg"], key="logo_uploader")
    if st.button("Attach Logo to Business", key="btn_attach_logo"):
        target=new_name.strip() or st.session_state.business_name
        if logo_file is None: st.warning("Choose a logo file first.")
        else:
            path=storage_save_logo(target, logo_file)
            if path:
                st.session_state.business_name=target
                st.session_state.current_logo_path=path
                st.session_state.profile["business"]={"name": target}
                st.success("Logo saved to profile."); st.rerun()
            else:
                st.error("Logo save failed.")

    st.markdown("---")
    st.caption(f"Storage: {'S3' if _storage_mode()=='s3' else 'Local files'}")

    st.markdown("---")
    st.markdown("### Year")
    year = st.number_input("Selected year", min_value=2000, max_value=2100, step=1, value=int(st.session_state.selected_year), key="sb_year")
    if st.button("Add / Ensure Year", key="btn_ensure_year"):
        st.session_state.selected_year=int(year)
        yb=st.session_state.profile.get("years",{}).get(str(year))
        goal=float(sum(s.get("TargetValue",0.0) for s in (yb or {}).get("revenue_streams", default_streams())))
        ensure_year_block(st.session_state.profile, int(year), goal)
        st.success(f"Year {year} ready."); st.rerun()

    st.markdown("---"); st.markdown("### Tracking – Quick Entry")
    q_month = st.selectbox("Month", options=MONTHS, index=0, key="qe_month")
    q_rev   = st.number_input("Revenue (actual)", min_value=0.0, value=0.0, step=1000.0, format="%0.0f", key="qe_rev")
    q_cogs  = st.number_input("Cost of sales (COGS)", min_value=0.0, value=0.0, step=1000.0, format="%0.0f", key="qe_cogs")
    q_oth   = st.number_input("Other overheads (this month)", min_value=0.0, value=0.0, step=1000.0, format="%0.0f", key="qe_oth")
    if st.button("Save Month Entry", key="btn_qe_save"):
        years=st.session_state.profile.setdefault("years",{})
        yk=str(st.session_state.selected_year)
        ensure_year_block(st.session_state.profile, int(yk), 0.0)
        ma=pd.DataFrame(years[yk]["monthly_actuals"]).set_index("Month")
        if q_month in ma.index:
            ma.at[q_month,"RevenueActual"]=q_rev
            ma.at[q_month,"CostOfSales"]=q_cogs
            ma.at[q_month,"OtherOverheads"]=q_oth
            years[yk]["monthly_actuals"]=ma.reset_index().to_dict(orient="records")
            st.success(f"Saved tracking for {q_month} {st.session_state.selected_year}")
        else:
            st.error("Month not found in table.")

col_logo, col_title = st.columns([1,3], vertical_alignment="center")
with col_logo:
    if st.session_state.current_logo_path and os.path.exists(st.session_state.current_logo_path):
        st.image(st.session_state.current_logo_path, use_container_width=True)
with col_title:
    st.title("Success Dynamics — Accountability Coach")
    st.caption("Profiles • Streams • Roles • Start Dates • Horizons • Tracking • Accountability")

profile=st.session_state.profile
yk=str(st.session_state.selected_year)
profile=ensure_year_block(profile, int(yk), 0.0)
year_block=profile["years"][yk]

with st.expander("Functions & Roles", expanded=False):
    func_col, roles_col = st.columns([1,3])
    with func_col:
        custom_func=st.text_input("Add a function", key="fn_add")
        c1,c2=st.columns(2)
        with c1:
            if st.button("➕ Add Function", key="btn_add_fn"):
                if custom_func.strip() and custom_func not in st.session_state.functions:
                    st.session_state.functions.append(custom_func.strip())
        with c2:
            if st.button("Reset to Core", key="btn_reset_core"):
                st.session_state.functions=CORE_FUNCTIONS.copy()
        st.caption("Current: "+", ".join(st.session_state.functions))
    with roles_col:
        df=st.session_state.roles_df
        for col in ROLE_COLUMNS:
            if col not in df.columns: df[col]=""
        df["FTE"]=pd.to_numeric(df["FTE"], errors="coerce").fillna(1.0).clip(0.0,1.0)
        edited=st.data_editor(
            df, num_rows="dynamic", use_container_width=True,
            column_config={
                "Function": st.column_config.SelectboxColumn(options=st.session_state.functions, required=True),
                "FTE": st.column_config.NumberColumn(min_value=0.0, max_value=1.0, step=0.1, format="%0.1f"),
                "KPIs": st.column_config.TextColumn(help="Comma‑separated list"),
                "Accountabilities": st.column_config.TextColumn(help="Bullets or lines"),
            },
            hide_index=True, key="roles_editor",
        )
        st.session_state.roles_df=edited

with st.expander("Revenue Streams (this year)", expanded=False):
    rev_df=pd.DataFrame(year_block.get("revenue_streams", default_streams()))
    for c in REVENUE_COLUMNS:
        if c not in rev_df.columns: rev_df[c]=""
    rev_df["TargetValue"]=pd.to_numeric(rev_df["TargetValue"], errors="coerce").fillna(0.0).clip(0.0)
    streams_total=float(rev_df["TargetValue"].sum())
    st.metric("Total of Streams", f"${streams_total:,.0f}")
    lock_goal=bool(year_block.get("lock_goal", True))
    revenue_goal = streams_total if lock_goal else float(year_block.get("revenue_goal", streams_total))
    rev_editor=st.data_editor(
        rev_df, num_rows="dynamic", use_container_width=True,
        column_config={
            "Stream": st.column_config.TextColumn(required=True),
            "TargetValue": st.column_config.NumberColumn(min_value=0.0, step=1000.0, format="%0.0f"),
            "Notes": st.column_config.TextColumn(),
        },
        hide_index=True, key="revenue_editor_year",
    )
    year_block["revenue_streams"]=rev_editor.fillna("").to_dict(orient="records")
    cols=st.columns(2)
    with cols[0]:
        lock_goal_ui=st.checkbox("Lock goal to streams total", value=lock_goal, key="chk_lock_goal")
    with cols[1]:
        revenue_goal=st.number_input("Revenue goal ($, this year)", min_value=0.0, value=float(revenue_goal), step=50000.0, format="%0.0f", disabled=lock_goal_ui, key="nb_revenue_goal")
    year_block["lock_goal"]=bool(lock_goal_ui)
    year_block["revenue_goal"]=float(streams_total if lock_goal_ui else revenue_goal)

with st.expander("Account Start Date & Horizon Goals", expanded=True):
    sd_str = year_block.get("account_start_date")
    if sd_str:
        try: sd_val = dt.date.fromisoformat(sd_str)
        except Exception: sd_val = dt.date(CUR_YEAR,1,1)
    else:
        sd_val = dt.date(CUR_YEAR,1,1)
    sd_new = st.date_input("Account Start Date (rolling 12 months)", value=sd_val, format="YYYY-MM-DD", key="di_start_date")
    year_block["account_start_date"]=sd_new.isoformat()

    st.caption("Horizon goals — targets for first 1/3/6/12 months (from Account Start Date).")
    hz=year_block.get("horizon_goals") or {"M1":None,"M3":None,"M6":None,"M12":None}
    default_hz={"M1": year_block["revenue_goal"]/12.0,
                "M3": year_block["revenue_goal"]*3/12.0,
                "M6": year_block["revenue_goal"]*6/12.0,
                "M12": year_block["revenue_goal"]}
    c1,c2,c3,c4=st.columns(4)
    with c1: hz["M1"]=st.number_input("1‑month goal", min_value=0.0, value=float(hz.get("M1") or default_hz["M1"]), step=1000.0, format="%0.0f", key="hz_m1")
    with c2: hz["M3"]=st.number_input("3‑month goal", min_value=0.0, value=float(hz.get("M3") or default_hz["M3"]), step=5000.0, format="%0.0f", key="hz_m3")
    with c3: hz["M6"]=st.number_input("6‑month goal", min_value=0.0, value=float(hz.get("M6") or default_hz["M6"]), step=10000.0, format="%0.0f", key="hz_m6")
    with c4: hz["M12"]=st.number_input("12‑month goal", min_value=0.0, value=float(hz.get("M12") or default_hz["M12"]), step=10000.0, format="%0.0f", key="hz_m12")
    year_block["horizon_goals"]=hz

with st.expander("People Costs (annual) — Start Month, Comment, ExtraMonthly", expanded=False):
    current_people=sorted(set(st.session_state.roles_df["Person"].dropna().astype(str).str.strip()) - {""})
    def default_people_costs(persons: list[str]) -> pd.DataFrame:
        return pd.DataFrame([{"Person": p, "AnnualCost": 0.0, "StartMonth": 1, "Comment":"", "ExtraMonthly": 0.0} for p in persons],
                            columns=["Person","AnnualCost","StartMonth","Comment","ExtraMonthly"])
    pc_df=pd.DataFrame(year_block.get("people_costs", [])) if year_block.get("people_costs") else default_people_costs(current_people)
    for p in current_people:
        if pc_df.empty or p not in set(pc_df["Person"]):
            pc_df=pd.concat([pc_df, pd.DataFrame([{"Person": p, "AnnualCost": 0.0, "StartMonth": 1, "Comment":"", "ExtraMonthly": 0.0}])], ignore_index=True)
    pc_df=pc_df.drop_duplicates(subset=["Person"]).reset_index(drop=True)

    vm_default=float(year_block.get("van_monthly_default", 1200.0))
    vm_default=st.number_input("Default Van/Vehicle monthly cost", min_value=0.0, value=vm_default, step=50.0, key="nb_van_default")
    year_block["van_monthly_default"]=vm_default

    def suggest_extra(row):
        comment=(str(row.get("Comment",""))).lower()
        extra=float(row.get("ExtraMonthly",0.0))
        if extra==0.0 and any(k in comment for k in ["van","vehicle","ute","truck"]):
            return vm_default
        return extra
    if not pc_df.empty:
        pc_df["ExtraMonthly"]=pc_df.apply(suggest_extra, axis=1)

    pc_edit=st.data_editor(
        pc_df, num_rows="dynamic", use_container_width=True,
        column_config={
            "Person": st.column_config.TextColumn(required=True),
            "AnnualCost": st.column_config.NumberColumn(min_value=0.0, step=1000.0, format="%0.0f"),
            "StartMonth": st.column_config.SelectboxColumn(options=list(range(1,13))),
            "Comment": st.column_config.TextColumn(help="e.g., 'tradie with a van', 'apprentice'"),
            "ExtraMonthly": st.column_config.NumberColumn(min_value=0.0, step=50.0, format="%0.0f"),
        },
        hide_index=True, key="people_costs_editor_year",
    )
    year_block["people_costs"]=pc_edit.fillna(0.0).to_dict(orient="records")

pc_edit=pd.DataFrame(year_block["people_costs"]) if year_block.get("people_costs") else pd.DataFrame(columns=["Person","AnnualCost","StartMonth","Comment","ExtraMonthly"])
per_person=[]
for _,row in pc_edit.iterrows():
    per_person.append((float(row.get("AnnualCost",0.0))/12.0, int(row.get("StartMonth",1)), float(row.get("ExtraMonthly",0.0))))
people_fixed_by_month=[]
for idx, m in enumerate(MONTHS, start=1):
    total=0.0
    for monthly, start_m, extra in per_person:
        if idx>=start_m:
            total += monthly + extra
    people_fixed_by_month.append(total)

with st.expander("Monthly Plan & Actuals", expanded=False):
    def default_monthly_plan(goal: float) -> pd.DataFrame:
        per=(goal or 0.0)/12.0
        return pd.DataFrame({"Month": MONTHS, "PlannedRevenue": [per]*12})
    def default_monthly_actuals() -> pd.DataFrame:
        return pd.DataFrame({"Month": MONTHS, "RevenueActual":[0.0]*12, "CostOfSales":[0.0]*12, "OtherOverheads":[0.0]*12})

    mp_df=pd.DataFrame(year_block.get("monthly_plan", default_monthly_plan(year_block.get("revenue_goal",0.0)).to_dict(orient="records")))
    if set(mp_df["Month"])!=set(MONTHS): mp_df=default_monthly_plan(year_block.get("revenue_goal",0.0))
    ma_df=pd.DataFrame(year_block.get("monthly_actuals", default_monthly_actuals().to_dict(orient="records")))
    if set(ma_df["Month"])!=set(MONTHS): ma_df=default_monthly_actuals()
    mp_edit=st.data_editor(
        mp_df, num_rows=12, use_container_width=True,
        column_config={
            "Month": st.column_config.SelectboxColumn(options=MONTHS),
            "PlannedRevenue": st.column_config.NumberColumn(min_value=0.0, step=1000.0, format="%0.0f"),
        },
        hide_index=True, key="monthly_plan_editor_year",
    )
    ma_edit=st.data_editor(
        ma_df, num_rows=12, use_container_width=True,
        column_config={
            "Month": st.column_config.SelectboxColumn(options=MONTHS),
            "RevenueActual": st.column_config.NumberColumn(min_value=0.0, step=1000.0, format="%0.0f"),
            "CostOfSales": st.column_config.NumberColumn(min_value=0.0, step=1000.0, format="%0.0f"),
            "OtherOverheads": st.column_config.NumberColumn(min_value=0.0, step=1000.0, format="%0.0f"),
        },
        hide_index=True, key="monthly_actuals_editor_year",
    )
    year_block["monthly_plan"]=mp_edit.fillna(0.0).to_dict(orient="records")
    year_block["monthly_actuals"]=ma_edit.fillna(0.0).to_dict(orient="records")

with st.expander("Accountability & Next Session", expanded=False):
    acct=year_block.get("accountability", {m: [] for m in MONTHS})
    st.caption("Action items to complete before next coaching session.")
    qa_cols=st.columns([1,2,1,1,1,2])
    with qa_cols[0]: a_month=st.selectbox("Month", options=MONTHS, key="acct_month")
    with qa_cols[1]: a_action=st.text_input("Action item", key="acct_action")
    with qa_cols[2]: a_owner=st.text_input("Owner", key="acct_owner")
    with qa_cols[3]: a_due=st.text_input("Due (YYYY-MM-DD)", key="acct_due")
    with qa_cols[4]: a_status=st.selectbox("Status", options=["Planned","Done","CarryOver"], key="acct_status")
    with qa_cols[5]: a_notes=st.text_input("Notes", key="acct_notes")
    if st.button("➕ Add accountability item", key="btn_add_acct"):
        acct.setdefault(a_month, []).append({"action":a_action,"owner":a_owner,"due":a_due,"status":a_status,"notes":a_notes})
        year_block["accountability"]=acct; st.success("Added item."); st.experimental_rerun()

    for m in MONTHS:
        items=acct.get(m, [])
        if not items: continue
        st.markdown(f"**{m}**")
        df_items=pd.DataFrame(items)
        df_items=st.data_editor(df_items, num_rows="dynamic", use_container_width=True, key=f"acct_editor_{m}")
        year_block["accountability"][m]=df_items.fillna("").to_dict(orient="records")

    st.markdown("---")
    st.caption("Next coaching session (advisory; check your calendar for final booking).")
    ns=year_block.get("next_session", {})
    ncols=st.columns([1,1,1,2,2])
    with ncols[0]: ns_month=st.selectbox("For month", options=MONTHS, key="ns_month")
    # Unique keys per field so there are no duplicates anywhere
    ns_defaults = ns.get(ns_month, {})
    with ncols[1]: ns_date=st.text_input("Date", value=ns_defaults.get("date",""), key=f"ns_date_{ns_month}")
    with ncols[2]: ns_time=st.text_input("Time", value=ns_defaults.get("time",""), key=f"ns_time_{ns_month}")
    with ncols[3]: ns_location=st.text_input("Location", value=ns_defaults.get("location",""), key=f"ns_loc_{ns_month}")
    with ncols[4]: ns_agreed=st.text_input("Agreed note", value=ns_defaults.get("agreed_note",""), key=f"ns_agreed_{ns_month}")
    ns_notes=st.text_input("Notes", value=ns_defaults.get("notes",""), key=f"ns_notes_{ns_month}")
    if st.button("💾 Save next session for month", key="btn_save_ns"):
        ns[ns_month]={"date":ns_date,"time":ns_time,"location":ns_location,"agreed_note":ns_agreed,"notes":ns_notes}
        year_block["next_session"]=ns; st.success("Saved next session.")

with st.expander("Dashboard & Charts", expanded=True):
    sd = year_block.get("account_start_date")
    if sd:
        try: start_month_idx = dt.date.fromisoformat(sd).month
        except Exception: start_month_idx = 1
    else:
        start_month_idx = 1
    ordered_months = rotate_months_from(start_month_idx)

    mp = pd.DataFrame(year_block["monthly_plan"]); ma = pd.DataFrame(year_block["monthly_actuals"])
    df_dash = mp.merge(ma, on="Month", how="left")
    df_dash["PeopleFixed"] = [people_fixed_by_month[MONTHS.index(m)] for m in df_dash["Month"]]
    df_dash["GrossMargin"] = (df_dash["RevenueActual"] - df_dash["CostOfSales"]).fillna(0.0)
    df_dash["OperatingProfit"] = (df_dash["GrossMargin"] - df_dash["PeopleFixed"] - df_dash["OtherOverheads"]).fillna(0.0)
    df_dash["MarginPct"] = df_dash.apply(lambda r: ((r["RevenueActual"]-r["CostOfSales"])/r["RevenueActual"]*100.0) if r["RevenueActual"]>0 else None, axis=1)
    df_dash["MIdx"] = df_dash["Month"].apply(lambda m: ordered_months.index(m))
    df_dash = df_dash.sort_values("MIdx").reset_index(drop=True)

    view_n = st.selectbox("View window (months from Start Date)", options=[1,3,6,12], index=3, key="sel_view_window")
    view_df = df_dash.head(view_n).copy()

    months_recorded=int(((view_df["RevenueActual"]>0)|(view_df["CostOfSales"]>0)|(view_df["OtherOverheads"]>0)).sum())
    win_revenue=float(view_df["RevenueActual"].sum())
    win_profit =float(view_df["OperatingProfit"].sum())
    st.metric("Window months (recorded)", months_recorded)
    cma, cmb = st.columns(2)
    with cma: st.metric("Revenue in window", f"${win_revenue:,.0f}")
    with cmb: st.metric("Operating Profit in window", f"${win_profit:,.0f}")

    valid_margins=[m for m in view_df["MarginPct"].tolist() if m is not None and m>0]
    fallback_margin=sum(valid_margins)/len(valid_margins) if valid_margins else 40.0
    def compute_break_even_row(row, people_fixed_monthly: float, fb: float=40.0):
        rev=float(row.get("RevenueActual",0.0)); cogs=float(row.get("CostOfSales",0.0)); other=float(row.get("OtherOverheads",0.0))
        margin_pct=((rev-cogs)/rev*100.0) if rev>0 else None
        if margin_pct is None or margin_pct<=0.0: margin_pct=fb
        mr=margin_pct/100.0
        return (people_fixed_monthly+other)/mr if mr>0 else None
    view_df["BreakEvenRevenue"]=view_df.apply(lambda r: compute_break_even_row(r, r["PeopleFixed"], fallback_margin), axis=1)

    hz=year_block.get("horizon_goals") or {}
    hz_target = hz.get({1:"M1",3:"M3",6:"M6",12:"M12"}[view_n]) or year_block["revenue_goal"] * (view_n/12.0)
    st.metric(f"Goal for {view_n}‑month window", f"${hz_target:,.0f}")

    st.write("**Revenue: Plan vs Actual vs Break‑even (window)**")
    st.line_chart(view_df.set_index("Month")[["PlannedRevenue","RevenueActual","BreakEvenRevenue"]])
    st.write("**Operating Profit with Margin % overlay (window)**")
    fig, ax1 = plt.subplots(figsize=(8,3))
    x=list(range(len(view_df)))
    ax1.bar(x, view_df["OperatingProfit"].fillna(0.0))
    ax1.set_xticks(x); ax1.set_xticklabels(view_df["Month"], rotation=45, ha="right")
    ax1.set_ylabel("Operating Profit ($)")
    ax2=ax1.twinx(); ax2.plot(x, [m if m is not None else float('nan') for m in view_df["MarginPct"]], marker="o")
    ax2.set_ylabel("Margin %")
    st.pyplot(fig, clear_figure=True)

with st.expander("Reports (PDF)", expanded=False):
    incl_revenue_streams = st.checkbox("Include Revenue Streams in Details PDF", value=True, key="chk_pdf_streams")
    incl_roles          = st.checkbox("Include Roles table in Details PDF", value=True, key="chk_pdf_roles")
    incl_people_costs   = st.checkbox("Include People Costs in Details PDF", value=True, key="chk_pdf_people")
    incl_plan_actuals   = st.checkbox("Include Monthly Plan & Actuals in Details PDF", value=True, key="chk_pdf_mon")

    mp_full=pd.DataFrame(year_block["monthly_plan"]); ma_full=pd.DataFrame(year_block["monthly_actuals"])
    df_full = mp_full.merge(ma_full, on="Month", how="left")
    df_full["PeopleFixed"] = [people_fixed_by_month[MONTHS.index(m)] for m in df_full["Month"]]
    df_full["GrossMargin"] = (df_full["RevenueActual"] - df_full["CostOfSales"]).fillna(0.0)
    df_full["OperatingProfit"] = (df_full["GrossMargin"] - df_full["PeopleFixed"] - df_full["OtherOverheads"]).fillna(0.0)
    df_full["MarginPct"] = df_full.apply(lambda r: ((r["RevenueActual"]-r["CostOfSales"])/r["RevenueActual"]*100.0) if r["RevenueActual"]>0 else None, axis=1)
    df_full["BreakEvenRevenue"] = df_full.apply(lambda r: ( (r["PeopleFixed"]+r["OtherOverheads"]) / ( ((r["RevenueActual"]-r["CostOfSales"])/r["RevenueActual"]) if r["RevenueActual"]>0 else 0.4 ) ) if True else None, axis=1)

    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        if st.button("Generate Tracking Report (PDF)", key="btn_pdf_tracking"):
            pdf_bytes = build_tracking_pdf(st.session_state.profile, st.session_state.selected_year, df_full, st.session_state.current_logo_path, year_block.get("accountability", default_accountability()), year_block.get("next_session", {}))
            st.download_button("Download Tracking Report PDF", data=pdf_bytes, file_name=f"tracking_{st.session_state.business_name}_{st.session_state.selected_year}.pdf", mime="application/pdf", key="dl_pdf_tracking")
    with col_dl2:
        if st.button("Generate Business Details (PDF)", key="btn_pdf_details"):
            include_flags={"streams":incl_revenue_streams,"roles":incl_roles,"people":incl_people_costs,"monthly":incl_plan_actuals}
            pdf_bytes = build_details_pdf(st.session_state.profile, st.session_state.selected_year, include_flags, st.session_state.current_logo_path)
            st.download_button("Download Business Details PDF", data=pdf_bytes, file_name=f"details_{st.session_state.business_name}_{st.session_state.selected_year}.pdf", mime="application/pdf", key="dl_pdf_details")

with st.expander("Structure & Visualisation (Org Chart)", expanded=False):
    roles_ser=st.session_state.roles_df["Role"].fillna("").astype(str).str.strip()
    if (roles_ser!="").sum()==0: st.info("Add at least one Role to render the chart.")
    else:
        dot=build_graphviz_dot(st.session_state.business_name, float(year_block.get("revenue_goal",0.0)), st.session_state.roles_df)
        st.graphviz_chart(dot, use_container_width=True)

st.session_state.profile["business"]={"name": st.session_state.business_name}
st.session_state.profile["functions"]=st.session_state.functions
st.session_state.profile["roles"]=st.session_state.roles_df.fillna("").to_dict(orient="records")
st.session_state.profile["years"][yk]=year_block

st.caption("© 2025 • Success Dynamics Accountability Coach • v7.1")
