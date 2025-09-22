# Success Dynamics Accountability Coach — v7

**New in v7**
- Per‑person **Comment** and **ExtraMonthly** cost (auto‑suggest if comment mentions van/vehicle).
- **Account Start Date** per year → rolling 12‑month period starting from that month.
- **Horizon goals (1/3/6/12)** editor and a dashboard **View window** selector (1, 3, 6, 12 months).
- All metrics and charts respect start date + selected window.
- Keeps: StartMonth per person, Accountability, Next Session, PDFs, S3 persistence, expanders.

## Quickstart
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Optional S3
Set env vars (in Streamlit Cloud Secrets or locally):
```
SD_STORAGE=s3
SD_S3_BUCKET=your-bucket
SD_S3_PREFIX=success_dynamics
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=ap-southeast-2
```

## Deploy (drag & drop)
Upload all files (including `data/`) to your GitHub repo. Folders include `.gitkeep` so they appear on GitHub.
