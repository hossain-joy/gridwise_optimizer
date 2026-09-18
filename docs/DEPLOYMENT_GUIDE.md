# GridWise — Public Cloud Deployment Guide

This guide provides step-by-step instructions for deploying the GridWise service to public cloud hosting platforms so that the evaluation endpoints (`GET /health` and `POST /optimize-energy`) are publicly accessible without authentication.

---

## 1. Cloud Deployment Options

### Option A: Render (Recommended — Fast & Free/Low-Cost)
1. Push your repository to GitHub.
2. In [Render Dashboard](https://dashboard.render.com/), click **New +** $\to$ **Web Service**.
3. Connect your GitHub repository.
4. Set the following configuration:
   - **Environment:** `Docker`
   - **Branch:** `main`
   - **Region:** Any (e.g., Oregon or Frankfurt)
   - **Instance Type:** Free / Starter
5. Under **Environment Variables**, add:
   - `PORT`: `8000`
   - `LLM_PROVIDER`: `gemini`
   - `LLM_MODEL`: `gemini-2.5-flash`
   - `LLM_API_KEY`: `your-google-ai-studio-api-key` (from https://aistudio.google.com/)
   - `LLM_BASE_URL`: `https://generativelanguage.googleapis.com/v1beta/openai/`
   *(Or leave empty to use the deterministic offline NLP fallback)*
6. Click **Deploy Web Service**.
7. Your public URL will be: `https://<service-name>.onrender.com`.

---

### Option B: Railway
1. Go to [Railway.app](https://railway.app/).
2. Click **New Project** $\to$ **Deploy from GitHub repo**.
3. Select your repository.
4. Railway automatically detects the `Dockerfile`.
5. Under **Variables**, add:
   - `PORT`: `8000`
   - `LLM_API_KEY`: `your-openai-api-key`
6. Under **Settings** $\to$ **Networking**, click **Generate Domain**.
7. Your public URL will be: `https://<service-name>.up.railway.app`.

---

### Option C: Fly.io
```bash
# 1. Install flyctl
curl -L https://fly.io/install.sh | sh

# 2. Authenticate
fly auth login

# 3. Launch application (from inside gridwise_optimizer directory)
fly launch --name gridwise-optimizer

# 4. Set secrets
fly secrets set LLM_API_KEY="sk-..." PORT="8000"

# 5. Deploy
fly deploy
```

---

### Option D: Google Cloud Run
```bash
# 1. Build and push image to Google Artifact Registry
gcloud builds submit --tag gcr.io/PROJECT_ID/gridwise:v1

# 2. Deploy to Cloud Run
gcloud run deploy gridwise \
  --image gcr.io/PROJECT_ID/gridwise:v1 \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars LLM_API_KEY="sk-..."
```

---

## 2. Post-Deployment Verification Checklist

Once deployed, run these verification checks against your public endpoint:

### Check 1: Health Probe
```bash
curl -i https://YOUR_BASE_URL/health
```
**Expected Response:**
```http
HTTP/2 200
Content-Type: application/json

{"status": "ok"}
```

### Check 2: Optimization Benchmark (Sample 1)
```bash
curl -X POST https://YOUR_BASE_URL/optimize-energy \
  -H "Content-Type: application/json" \
  -d '{
    "scenario_id": "SAMPLE-01",
    "operator_notes": [
      "Facilities will wash the rooftop solar panels from noon until 2 PM. During cleaning, usable solar should be treated as roughly 25% of the forecast.",
      "The sports office moved next month'\''s registration deadline."
    ],
    "hours": [...],
    "battery": {
      "capacity_kwh": 220,
      "initial_energy_kwh": 110,
      "minimum_energy_kwh": 40,
      "max_charge_kwh_per_hour": 50,
      "max_discharge_kwh_per_hour": 50
    }
  }'
```
**Expected Verification:**
- HTTP status `200 OK`.
- Response contains exact `scenario_id`.
- Directive 0 has `solar_reduction` with `factor: 0.25` for hours `[12, 13]`.
- Directive 1 has `no_op` with `applies: false` and `structured_adjustment: null`.
- `total_cost_bdt` equals `38365.0`.
