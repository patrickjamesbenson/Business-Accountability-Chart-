# Success Dynamics Accountability Chart (Streamlit)

A ready-to-deploy Streamlit app that builds an Accountability Chart aligned to the Success Dynamics process.

## Features
- **Revenue Streams** editor (New Clients, Subscriptions, Upsell, etc.) with total roll-up and optional lock to the 12‑month goal.
- **Functions & Roles:** Sales & Marketing, Operations, Finance (+ add more). Inline table for Role, Person, FTE, ReportsTo, KPIs, Accountabilities.
- **Visual Tree:** Graphviz diagram with functions as clusters and roles as nodes; `ReportsTo` draws reporting lines.
- **Import/Export:** Full JSON (business, functions, roles, revenue_streams) and CSV template for roles.
- **Branding:** Sidebar logo uploader (PNG/JPG/SVG).

## Quickstart
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Cloud
1. Push this folder to a GitHub repo.
2. Create a new Streamlit app and select `app.py` as the entry point.
3. Set Python version >=3.10.
