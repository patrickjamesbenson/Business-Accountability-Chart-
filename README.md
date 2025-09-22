# Tracking Success — v7.5

**New in this build**
- **UpCoach webhooks:** Enter a webhook URL in **Admin → Integrations**. We POST JSON on `task.created` and `task.updated`.
- **Email invites with “Complete” button:** Set **App Base URL**; each task shows an **Email invite (.eml)** download with a HTML button linking to the one‑click completion token.
- **Customer Journey Mapping (beta):** In **Admin → Customer Journey Mapping**, add/delete stages (columns), edit elements (Actions, Touchpoints, Emotions, PainPoints, Solutions), save, and export to **PDF** or **JSON**. Pre‑filled examples included.

**Run**
```bash
pip install -r requirements.txt
streamlit run app.py
```

**Deploy**
Upload all files (keep the `data/` folder) to your GitHub repo. On Streamlit Cloud, set the entry point to `app.py`.
