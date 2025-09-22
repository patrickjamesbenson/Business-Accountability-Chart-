# Tracking Success — Full v7.7c

All‑in‑one Streamlit app for accountability charts, tracking, reports, coaching assets, tasks with completion links, Push Sync (UpCoach, Calendly, Email), journey mapping, mission & values, and a trade profit calculator.

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy (Streamlit Cloud)
- Repo must include `app.py`, `requirements.txt`, and the `data/` folder.
- Entry point: **app.py**
- After deploy, open the app and set your `App Base URL` in **Integrations** so task completion links work.

## Folders
- `data/profiles/` — JSON profiles (one per business)
- `data/logos/` — uploaded logos (tied to business name)
- `data/assets/` — screenshots for coaching reports

## Feature map
- **Profiles:** Open / Save / Save As / Delete (in sidebar).
- **Branding:** Upload a logo under business name.
- **Start Date:** The account start date controls the 12‑month view (rotates months and run‑rate).
- **Revenue Streams:** Define streams and targets; option to lock total to annual goal.
- **Organisation:** Functions → Roles/People (drives people list).
- **People Costs:** Annual cost, Start month, Van toggle or ExtraMonthly ($).
- **Tracking Quick Entry:** Update monthly Revenue, CoS, Overheads.
- **Dashboard & Reports:** Charts (Planned vs Actual vs Break‑even; Profit + Margin%). Export Tracking/Details PDFs.
- **Coaching Assets:** Notes, URLs & screenshots, each with “include in report” toggle.
- **Tasks:** Create tasks with one‑click **Completion links**.
- **Push Sync:** Send a summary payload to **UpCoach**, share **Calendly** link, and/or email a copy.
- **Mission & Values:** Authentic prompts and storage for mission, values, principles.
- **Customer Journey:** Editable stages/columns with dynamic rows.
- **Trade Profit Calculator:** Estimate required blended rate + per‑person contribution.

