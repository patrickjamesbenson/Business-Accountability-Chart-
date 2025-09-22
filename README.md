# Tracking Success — v7.4

**New in this build**
- **Coaching Notes — Uploads & Links**: attach screenshots (PNG/JPG) and URLs **per month**, each with **Include in report** toggles.
- **Tasks module**: quick-create tasks with common templates, assign to people (from your Organisation/People Costs), due date, notes, and an **Include in report** toggle.
- **One‑click completion**: each task has a **Completion link** (`?complete_task=TOKEN`). Share that link with the assignee; opening the app with it marks the task **Done** automatically.
- **Reports**: Tracking PDF now includes **Coaching evidence** (only items you marked *Include in report*) and **Tasks** (included only).

**Run**
```bash
pip install -r requirements.txt
streamlit run app.py
```

**Deploy**
Upload all files (keep the `data/` folder) to your GitHub repo. On Streamlit Cloud, set the entry point to `app.py`.
