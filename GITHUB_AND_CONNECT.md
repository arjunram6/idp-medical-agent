# How to Create and Connect Your GitHub Repo (idp-medical-agent)

Two parts: **(1)** put your project on GitHub, **(2)** connect that repo to Render or Railway so they can deploy it.

---

## Part 1: Put Your Project on GitHub

### If you don’t have a GitHub account yet

1. Go to [github.com](https://github.com) and **Sign up**.
2. Verify your email if asked.

### Create a new repository on GitHub

1. Log in to GitHub.
2. Click the **+** (top right) → **New repository**.
3. Fill in:
   - **Repository name:** `idp-medical-agent` (or any name you like).
   - **Description:** optional, e.g. "IDP Medical Agent – Ghana facility API".
   - **Public** (so Render/Railway can access it).
   - **Do not** check "Add a README" or "Add .gitignore" if your folder already has them.
4. Click **Create repository**.
5. GitHub will show a page with a URL like:  
   `https://github.com/YOUR_USERNAME/idp-medical-agent.git`  
   Keep this URL; you’ll use it in the next step.

### Push your local project to GitHub

Do this from your **computer**, in the folder where your project lives (the one with `main.py`, `api.py`, `src/`, etc.).

**Option A: This folder is not a git repo yet**

Open Terminal (or Command Prompt) and run (replace `YOUR_USERNAME` with your GitHub username):

```bash
cd /path/to/idp-medical-agent
git init
git add .
git commit -m "Initial commit: IDP Medical Agent API"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/idp-medical-agent.git
git push -u origin main
```

If GitHub asks for a password, use a **Personal Access Token** (see below).

**Option B: This folder is already a git repo**

If you already ran `git init` and have commits:

```bash
cd /path/to/idp-medical-agent
git remote add origin https://github.com/YOUR_USERNAME/idp-medical-agent.git
git branch -M main
git push -u origin main
```

(If `origin` already exists, use `git remote set-url origin https://github.com/YOUR_USERNAME/idp-medical-agent.git` then `git push -u origin main`.)

**GitHub password / Personal Access Token**

- GitHub no longer accepts account passwords for `git push`.
- Create a token: GitHub → **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)** → **Generate new token**. Give it a name, tick **repo**, then generate and **copy the token**.
- When you run `git push`, use your **GitHub username** and, when it asks for a password, **paste the token**.

After this, your code is on GitHub at `https://github.com/YOUR_USERNAME/idp-medical-agent`.

---

## Part 2: Connect the Repo to Render or Railway

### Connect to Render

1. Go to [render.com](https://render.com) and **Sign up** (or Log in).
2. Choose **Sign up with GitHub** so Render can see your repos.
3. Authorize Render when GitHub asks (“Authorize Render”).
4. In the Render dashboard: **New +** → **Web Service**.
5. Under **Connect a repository**, you should see a list of your GitHub repos.
6. Click **Connect** next to **idp-medical-agent** (or search for it). If you don’t see it, click **Configure account** and make sure Render has access to the repo or to “All repositories”.
7. After you select **idp-medical-agent**, Render will show settings (build command, start command, env vars). Add **OPENAI_API_KEY** in Environment, then click **Create Web Service**.

Your GitHub repo is now **connected**: Render will build and deploy from that repo, and future pushes to `main` can auto-deploy if you turn that on.

### Connect to Railway

1. Go to [railway.app](https://railway.app) and **Sign up** (or Log in).
2. Choose **Login with GitHub** so Railway can see your repos.
3. **New Project** → **Deploy from GitHub repo**.
4. You’ll see a list of your GitHub repos. Click **idp-medical-agent** (or the name you used). If it’s missing, click **Configure GitHub App** and grant Railway access to that repo or all repos.
5. Railway will create a project and start deploying. Add **OPENAI_API_KEY** in the service **Variables**, then trigger a redeploy if needed.

Your GitHub repo is now **connected** to Railway.

---

## Quick Reference

| Step | What to do |
|------|------------|
| 1 | Create repo on GitHub: **+** → **New repository** → name it `idp-medical-agent` → **Create repository** |
| 2 | On your machine: `cd` to project → `git init` (if needed) → `git add .` → `git commit -m "Initial commit"` → `git remote add origin https://github.com/YOUR_USERNAME/idp-medical-agent.git` → `git push -u origin main` |
| 3 | Render: **Sign up with GitHub** → **New Web Service** → **Connect** → choose **idp-medical-agent** → add OPENAI_API_KEY → **Create Web Service** |
| 4 | Railway: **Login with GitHub** → **New Project** → **Deploy from GitHub repo** → choose **idp-medical-agent** → add OPENAI_API_KEY |

---

## If You Don’t Want to Use GitHub

You can still deploy:

- **Render:** **New +** → **Web Service** → **Build and deploy from a repository** can sometimes connect to GitLab or other sources; or use **Manual deploy** and upload a zip (less ideal for updates).
- **Railway:** Prefers a connected repo; you can also try **Deploy from local** or a zip if they support it.

For the smoothest flow (and “connect your GitHub repo”), creating the repo on GitHub and pushing your **idp-medical-agent** folder, then connecting that repo in Render or Railway, is the standard approach.
