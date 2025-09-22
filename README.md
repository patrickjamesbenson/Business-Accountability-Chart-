# Success Dynamics Accountability Coach — v7.1

**Fixes**
- Resolved `StreamlitDuplicateElementId` by adding **unique `key=`** values to all repeated widget labels
  (notably the two different **"Notes"** inputs and the Next Session fields).

**Features (from v7)**
- People Comments & ExtraMonthly (auto-suggest for vans/vehicles)
- Account Start Date (rolling 12 months) & Horizon goals (1/3/6/12)
- View window selector; charts/metrics respect Start Date + window
- Accountability, Next Session, PDFs, S3 persistence, expanders

## Run
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy
Drag & drop everything to GitHub. In Streamlit Cloud, set app entrypoint to `app.py`.
