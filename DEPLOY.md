# Deploy the IDP Medical Agent API

You can deploy the API so it has a **public URL** (e.g. `https://your-app.onrender.com`) that the Lovable frontend (or anyone) can call. Below are two options that work with the config files in this repo.

---

## Option 1: Render (free tier)

1. **Sign up:** [render.com](https://render.com) (free account).
2. **New Web Service:** Dashboard → **New +** → **Web Service**.
3. **Connect repo:** Connect your GitHub/GitLab and select the **idp-medical-agent** repo (or upload the zip and let Render clone from your connected repo).
4. **Settings (if not using render.yaml):**
   - **Runtime:** Python 3
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn api:app --host 0.0.0.0 --port $PORT`
   - **Instance type:** Free (or paid if you prefer)
5. **Environment:** Add variable **`OPENAI_API_KEY`** = your OpenAI API key (secret).
6. **Deploy:** Click **Create Web Service**. Render will build and run the API.
7. **Your API URL:** After deploy, Render shows a URL like `https://idp-medical-agent-api.onrender.com`. That is your **API URL** – give it to the Lovable integration person.

**If you use the included `render.yaml`:** Connect the repo, then add a **Blueprint** and point it at `render.yaml` (or create the service and Render may auto-detect it). Add `OPENAI_API_KEY` in the dashboard.

---

## Option 2: Railway (free tier / trial)

1. **Sign up:** [railway.app](https://railway.app) (free trial, then usage-based).
2. **New project:** **New Project** → **Deploy from GitHub repo** (or upload code).
3. **Select repo:** Choose the **idp-medical-agent** repo.
4. **Settings:** Railway usually detects Python and uses the **Procfile** (`web: uvicorn api:app --host 0.0.0.0 --port $PORT`). If not, set **Start Command** to:
   `uvicorn api:app --host 0.0.0.0 --port $PORT`
5. **Environment:** In the service → **Variables**, add **`OPENAI_API_KEY`** = your OpenAI API key.
6. **Deploy:** Railway builds and deploys. Then open **Settings** → **Networking** → **Generate domain**. You get a URL like `https://idp-medical-agent-api-production.up.railway.app`. That is your **API URL**.

---

## Data (Ghana CSV) on the server

The API expects the Ghana facility CSV (and optional scheme doc) in the **data/** folder or as configured in the app. For a deployed server:

- **Option A:** Commit a **sample or anonymized** CSV into the repo under `data/` so the deployed app has data. (Don’t commit sensitive data.)
- **Option B:** Mount external storage (e.g. Render disk, S3) and point the app at that path (would require a small code/config change to set `DATA_DIR` or load from URL).
- **Option C:** Run the API without CSV; it will still start, but queries that need the CSV will return “No Ghana CSV found” until you add the file.

For a quick deploy, putting a non-sensitive CSV in `data/` and committing it is the simplest.

---

## After deploy

- **API URL:** Use the URL Render or Railway gives you (e.g. `https://idp-medical-agent-api.onrender.com`).
- **Health check:** Open `https://your-api-url/api/health` in a browser – you should see `{"status":"ok", ...}`.
- **Docs:** Open `https://your-api-url/docs` for Swagger UI.
- **Lovable:** Give the **API URL** (no trailing slash) to the person doing the Lovable integration so they set it as the base URL in the frontend.

---

## Summary

| Step | Render | Railway |
|------|--------|---------|
| 1 | render.com → New Web Service | railway.app → New Project → Deploy from repo |
| 2 | Connect repo, set build/start (or use render.yaml) | Repo uses Procfile automatically |
| 3 | Add OPENAI_API_KEY in Environment | Add OPENAI_API_KEY in Variables |
| 4 | Deploy → copy service URL | Generate domain → copy URL |
| **Your API URL** | `https://xxx.onrender.com` | `https://xxx.up.railway.app` |

I can’t log into your Render or Railway account, so you’ll need to do these steps yourself. Once the service is deployed, that URL is your **API URL** for the Lovable frontend.
