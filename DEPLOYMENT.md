# CiteRag — Deployment Guide

Complete step-by-step guide to deploy:
- **Backend** (FastAPI + Docker) → **Railway** (free tier)
- **Frontend** (static HTML) → **Netlify** (free forever)

---

## Before You Start — Cloud Services Required

All three services have free tiers that are sufficient for this project.

| Service | What You Need | Sign-up Link |
|---|---|---|
| **MongoDB Atlas** | Free M0 cluster + connection string | https://www.mongodb.com/cloud/atlas |
| **Qdrant Cloud** | Free 1 GB cluster + URL + API key | https://cloud.qdrant.io |
| **Groq** | Free developer API key | https://console.groq.com |
| **LangSmith** | Free API key (optional — for tracing) | https://smith.langchain.com |
| **Railway** | Free account ($5/mo credit) | https://railway.app |
| **Netlify** | Free account | https://netlify.com |

---

## Step 1 — Prepare Your Credentials

Collect the following values before you start:

```
MONGODB_URL       = mongodb+srv://<user>:<password>@cluster.mongodb.net/?appName=...
QDRANT_URL        = https://<cluster-id>.aws.cloud.qdrant.io
QDRANT_API_KEY    = eyJhbGci...
GROQ_API_KEY      = gsk_...
LANGCHAIN_API_KEY = lsv2_pt_...   (optional)
```

---

## Step 2 — Push to GitHub

Make sure all your latest changes are committed and pushed:

```bash
cd d:\projectaalphaa\CiteRag

git add .
git commit -m "ready for deployment"
git push origin main
```

---

## Step 3 — Deploy Backend to Railway

### 3.1 — Create a Railway account
Go to [railway.app](https://railway.app) and sign up (GitHub login recommended).

### 3.2 — Create a new project
1. Click **New Project**
2. Choose **Deploy from GitHub repo**
3. Authorize Railway to access your GitHub
4. Select your **CiteRag** repository

### 3.3 — Set the root directory
Railway deploys from the repo root by default. You need to point it at the `backend/` folder:

1. In your newly created Railway service, go to **Settings**
2. Under **Source** → set **Root Directory** to `backend`
3. Railway will auto-detect the `Dockerfile` inside `backend/`

### 3.4 — Add environment variables
Go to the **Variables** tab and add each variable:

| Variable | Value |
|---|---|
| `MONGODB_URL` | Your Atlas connection string |
| `QDRANT_URL` | Your Qdrant cluster URL |
| `QDRANT_API_KEY` | Your Qdrant API key |
| `GROQ_API_KEY` | Your Groq API key |
| `COHERE_API_KEY` | Your Cohere API key |
| `EMBEDDING_MODEL` | `embed-english-v3.0` |
| `RERANKER_MODEL` | `rerank-v3.5` |
| `LLM_MODEL` | `llama-3.1-8b-instant` |
| `CHUNK_SIZE` | `512` |
| `CHUNK_OVERLAP` | `128` |
| `BM25_TOP_K` | `20` |
| `VECTOR_TOP_K` | `20` |
| `RERANKER_TOP_K` | `10` |
| `CONFIDENCE_THRESHOLD` | `0.30` |
| `UPLOAD_DIR` | `uploads` |
| `MAX_FILE_SIZE_MB` | `50` |
| `LANGCHAIN_TRACING_V2` | `true` |
| `LANGCHAIN_API_KEY` | Your LangSmith key |
| `LANGCHAIN_PROJECT` | `cite_rag` |
| `LANGCHAIN_ENDPOINT` | `https://api.smith.langchain.com` |

> Railway automatically injects `PORT` — the Dockerfile already uses `${PORT:-8000}` so no action needed.

### 3.5 — Deploy
Click **Deploy**. Railway will:
1. Pull your code from GitHub
2. Build the Docker image (5–15 min first time — downloads ML models ~2.3 GB)
3. Start the container and expose a public HTTPS URL

### 3.6 — Verify the backend
Once deployed, copy your Railway URL (e.g. `https://citerag-backend.up.railway.app`) and visit:

```
https://your-railway-url.up.railway.app/api/health
```

Expected response:
```json
{"status": "ok", "service": "CiteRag API", "version": "0.1.0"}
```

Also visit `/docs` for the interactive Swagger UI.

---

## Step 4 — Deploy Frontend to Netlify

The frontend is a **single static HTML file** — no build, no npm, no framework.

### Option A — Drag and Drop (30 seconds)

1. Go to [app.netlify.com/drop](https://app.netlify.com/drop)
2. Drag the entire `frontend/` folder onto the page
3. Netlify instantly publishes it at a URL like `https://magical-cupcake-123456.netlify.app`
4. *(Optional)* Click **Site configuration → Change site name** for a cleaner URL

### Option B — GitHub Integration (Auto-deploy on every push)

1. Go to [app.netlify.com](https://app.netlify.com)
2. Click **Add new site → Import an existing project**
3. Connect to your GitHub and select the **CiteRag** repository
4. Set build settings:

   | Setting | Value |
   |---|---|
   | Base directory | `frontend` |
   | Build command | *(leave blank)* |
   | Publish directory | `frontend` |

5. Click **Deploy site**

---

## Step 5 — Connect Frontend to Backend

Once both services are live:

1. Open your Netlify URL in the browser
2. Click the **status dot** (top-right of the app) — the Settings modal opens
3. Paste your Railway URL: `https://your-app.up.railway.app`
4. Click **Save**

The frontend saves this in `localStorage` — users only need to set it once per browser.

### Make the Railway URL the default

To avoid every new user having to configure the URL, edit `frontend/index.html` line 488:

```js
// Change this:
let BACKEND = localStorage.getItem('citerag_backend') || 'http://localhost:8000';

// To this (your actual Railway URL):
let BACKEND = localStorage.getItem('citerag_backend') || 'https://your-app.up.railway.app';
```

Then push to GitHub → Netlify auto-redeploys.

---

## Post-Deployment Checklist

Run through this after both services are live:

- [ ] `GET /api/health` returns `{"status":"ok"}`
- [ ] Frontend loads and shows green **"Backend connected"** status dot
- [ ] Upload a PDF → status changes `processing` → `ready`
- [ ] Submit a question in **Liberal Mode** → answer + citations appear
- [ ] Submit a question in **Strict Mode** → confidence score shown
- [ ] Click 👁 on a citation → highlighted PDF page renders
- [ ] Rename a document → name updates in the sidebar
- [ ] Delete a document → removed from sidebar and all databases
- [ ] LangSmith dashboard shows traces (if `LANGCHAIN_TRACING_V2=true`)

---

## Automatic Re-deploys

| Trigger | Effect |
|---|---|
| Push to `main` branch | Netlify re-deploys frontend immediately |
| Push to `main` branch | Railway rebuilds Docker image and redeploys backend |

No manual action needed for updates — just `git push`.

---

## Railway Free Tier Notes

| Resource | Free Tier Limit |
|---|---|
| Compute | $5 credit / month (~500 container hours) |
| RAM | 512 MB |
| Disk | Ephemeral — **uploads are lost on redeploy** |
| Bandwidth | 100 GB / month |

> **Uploads are ephemeral on Railway's free tier.** Uploaded files live in the container's `/app/uploads/` directory and are deleted when Railway redeploys or restarts the container. The document metadata and chunk vectors in MongoDB + Qdrant Cloud **are persistent** — only the original source files are lost. For a portfolio demo this is fine. For production use, integrate S3 or Cloudflare R2 for file storage.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Railway build fails at pip install | Check `requirements.txt` has no blank lines |
| `ModuleNotFoundError` on startup | Ensure **Root Directory** is set to `backend` in Railway |
| Frontend shows "Not connected" | Check the backend URL in Settings has no trailing slash |
| Upload succeeds but status stays `processing` | Check Railway logs — likely a Qdrant or MongoDB connection error |
| PDF highlight returns 404 | The original file was lost due to Railway ephemeral disk — re-upload the document |
| Very slow cold start (~3–5 min) | Models download at first boot on free tier — upgrade for faster starts |
