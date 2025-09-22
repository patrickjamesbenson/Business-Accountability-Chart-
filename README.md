# Success Dynamics Accountability Chart (Streamlit) — v3

**What’s new**
- Top header logo + per-profile logo persistence
- **Profiles**: Save / Save As / Open, and **Delete** (removes JSON + linked logo)
- Auto‑rerun on profile actions so the header + state refresh
- `data/profiles` and `data/logos` include `.gitkeep` so GitHub drag‑drop keeps folders

## Quickstart
```bash
pip install -r requirements.txt
streamlit run app.py
```

## GitHub Upload (drag & drop)
1. Download / unzip this folder locally.
2. On GitHub, click **Add file → Upload files**.
3. Drag the **entire folder contents** (all files + the `data` folder) into the upload window.
   - Because we include `.gitkeep`, GitHub will create the `data/profiles` and `data/logos` folders.
4. Commit the upload.

If GitHub refuses folder drag‑drop in your browser, create them manually:
- Click **Add file → Create new file** and type `data/profiles/.gitkeep` then **Commit**.
- Repeat for `data/logos/.gitkeep`.
- Then upload the rest of the files normally.

## Optional: one‑time push via Git (Windows PowerShell)
```powershell
# Edit these first:
$RepoUrl = "https://github.com/USERNAME/REPO.git"

# Run in the unzipped folder:
git init
git add .
git commit -m "Initial commit: Success Dynamics Accountability Chart v3"
git branch -M main
git remote add origin $RepoUrl
git push -u origin main
```

## Persistence note
Local JSON & logo files persist on your computer/server. On Streamlit Cloud, local `./data` is ephemeral; for long‑term storage, connect S3/Drive/DB later.
