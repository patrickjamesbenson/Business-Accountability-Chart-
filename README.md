# Success Dynamics Accountability Chart (Streamlit) — v2

Adds top-of-page branding and profile persistence by business name.

## New in v2
- Top header shows the uploaded **Success Dynamics** logo (also saved per profile).
- **Business Profiles**: save/load by name to `./data/profiles/*.json`. Logos go to `./data/logos/`.
- Goal can be **locked** to the sum of revenue streams or set manually.

## Quickstart
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy
- Push to GitHub and deploy on Streamlit Cloud (or run locally).
- Note on Streamlit Cloud: local file writes in `./data` persist only for the container lifetime.
  For long‑term persistence across restarts, connect external storage (S3, GDrive, DB).
