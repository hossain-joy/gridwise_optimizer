# GridWise — LLM-Assisted Energy Optimizer (v2.0)

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688.svg)](https://fastapi.tiangolo.com/)
[![PuLP](https://img.shields.io/badge/PuLP-Linear%20Programming-orange.svg)](https://coin-or.github.io/pulp/)
[![Live Cloud](https://img.shields.io/badge/Live%20Demo-Render-brightgreen.svg)](https://voltss.onrender.com/)
[![Tests](https://img.shields.io/badge/Tests-100%20Passing%20(100%25)-brightgreen.svg)]()

Production-grade, resilient FastAPI backend and interactive Dribbble-inspired SaaS dashboard for 24-hour campus energy schedule optimization. Designed for the **BUP CSE Fest 2026 Hackathon (Online Preliminary)**.

---

## 🌐 Live Cloud Deployment

- **Live Interactive Dashboard:** [https://voltss.onrender.com/](https://voltss.onrender.com/)
- **Swagger OpenAPI Docs:** [https://voltss.onrender.com/docs](https://voltss.onrender.com/docs)
- **Health Check Endpoint:** [https://voltss.onrender.com/health](https://voltss.onrender.com/health)

---

## ⚡ Key Highlights

- **Decoupled 5-Stage Architecture:** Strictly isolates untrusted LLM interpretation from deterministic mathematical linear programming and physical constraint validation.
- **100% Benchmark Accuracy:** Validated against all 10 official public sample cases + 90 synthetic stress scenarios (100/100 passing, 2,400 hours physically verified) with zero error in directive interpretation, energy conservation, and cost minimization.
- **Zero-Downtime Resilience:** Features dual-model failover, in-memory prompt caching (0ms hit latency), and an intelligent deterministic NLP fallback for offline execution.
- **Optimal Tie-Breaking:** Employs a negligible peak penalty ($\epsilon = 10^{-5}$) to break dispatch ties across identical tariff hours, smoothing peak import while guaranteeing minimal cost.
- **Physical Safety Replay:** Independently re-computes and asserts energy balance, battery limits, rate constraints, and end-of-day neutrality ($SoC_{23} = SoC_{initial}$) before responding.
- **Interactive Modern UI/UX:** Dribbble-grade SaaS dashboard with 1-click scenario switching, Chart.js 24h stacked dispatch profile, live directives breakdown, table action filters, CSV/JSON data export, and keyboard shortcuts (`⌘K` / `Ctrl+Enter`).

---

## 📐 Architecture at a Glance

```
Energy Data + Operator Notes
        ↓
[1] LLM Interpreter    → Extracts structured directive types (JSON mode, Cache, Offline NLP Fallback)
        ↓
[2] Guardrail Validator → Pure Python validation: enforces bounds & downgrades invalid outputs to `no_op`
        ↓
[3] Math Optimizer      → PuLP Linear Programming (CBC solver) guarantees global minimum cost
        ↓
[4] Final Validator     → Safety replay layer verifying physical constraints & energy balance (TOL <= 0.01)
        ↓
API Response (200 OK)
```

---

## 📚 Documentation Index

- [**System Architecture (`docs/ARCHITECTURE.md`)**](docs/ARCHITECTURE.md): In-depth 5-stage pipeline walkthrough, LP mathematical formulation, and caching mechanics.
- [**Directives Specification (`docs/DIRECTIVES_SPEC.md`)**](docs/DIRECTIVES_SPEC.md): Complete schema, semantics, and time window rules for all 6 directives.
- [**API Reference (`docs/API_REFERENCE.md`)**](docs/API_REFERENCE.md): Full endpoint specs, request/response models, status codes, and code examples.
- [**Testing & Benchmarks (`docs/TESTING_AND_BENCHMARKS.md`)**](docs/TESTING_AND_BENCHMARKS.md): Full test suite instructions, benchmark outputs, and compliance checklists.
- [**Deployment Guide (`docs/DEPLOYMENT_GUIDE.md`)**](docs/DEPLOYMENT_GUIDE.md): Complete guide for Docker, Render, and cloud hosting.

---

## 🚀 Quickstart

### 1. Prerequisites
- Python 3.11+
- `coinor-cbc` solver (included in Docker or via system package manager: `brew install cbc` on macOS, `apt install coinor-cbc` on Linux)

### 2. Environment Setup
```bash
# Clone and enter directory
git clone https://github.com/hossain-joy/gridwise_optimizer.git
cd gridwise_optimizer

# Create and activate virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\Activate.ps1
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Variables (Optional for LLM Mode)
Copy `.env.example` to `.env`:
```env
PORT=8000
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.5-flash
LLM_API_KEY=your_gemini_api_key_here
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
```
*(Note: If `LLM_API_KEY` is not provided, the service automatically utilizes the deterministic NLP fallback extractor.)*

### 4. Start Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
- API Docs: `http://localhost:8000/docs`
- Interactive Dashboard: `http://localhost:8000/` or `http://localhost:8000/demo`
- Health Probe: `http://localhost:8000/health`

---

## 🧪 Running the Automated Test Suites

```bash
# 1. Run all unit, fuzz, guardrail, and sample pack integration tests (53 tests)
python -m pytest tests/ -v

# 2. Run the 10-case official sample evaluation benchmark
python -m tests.run_official_sample_evaluation

# 3. Run the 100-scenario comprehensive stress & physical replay audit (2,400 hours)
python -m tests.test_100_scenarios
```

---

## 🐳 Docker Deployment

```bash
# Build image
docker build -t gridwise-optimizer .

# Run container
docker run -d -p 8000:8000 --name gridwise gridwise-optimizer
```
