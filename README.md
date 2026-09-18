# GridWise — LLM-Assisted Energy Optimizer (v2.0)

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688.svg)](https://fastapi.tiangolo.com/)
[![PuLP](https://img.shields.io/badge/PuLP-Linear%20Programming-orange.svg)](https://coin-or.github.io/pulp/)
[![Tests](https://img.shields.io/badge/Tests-23%20Passing-brightgreen.svg)]()

Production-grade, resilient FastAPI backend for 24-hour campus energy schedule optimization. Designed for the **BUP CSE Fest 2026 Hackathon (Online Preliminary)**.

---

## Key Highlights

- **Decoupled 5-Stage Architecture:** Strictly isolates untrusted LLM interpretation from deterministic mathematical linear programming and physical constraint validation.
- **100% Benchmark Accuracy:** Validated against all 10 official public sample cases with zero error in directive interpretation, energy conservation, and cost minimization.
- **Zero-Downtime Resilience:** Features dual-model failover, in-memory prompt caching (0ms hit latency), and an intelligent deterministic NLP fallback for offline execution.
- **Optimal Tie-Breaking:** Employs a negligible peak penalty ($\epsilon = 10^{-5}$) to break dispatch ties across identical tariff hours, smoothing peak import while guaranteeing minimal cost.
- **Physical Safety Replay:** Independently re-computes and asserts energy balance, battery limits, rate constraints, and end-of-day neutrality ($SoC_{23} = SoC_{initial}$) before responding.

---

## Architecture at a Glance

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

## Documentation Index

- [**System Architecture (`docs/ARCHITECTURE.md`)**](docs/ARCHITECTURE.md): In-depth 5-stage pipeline walkthrough, LP mathematical formulation, and caching mechanics.
- [**Directives Specification (`docs/DIRECTIVES_SPEC.md`)**](docs/DIRECTIVES_SPEC.md): Complete schema, semantics, and time window rules for all 6 directives.
- [**API Reference (`docs/API_REFERENCE.md`)**](docs/API_REFERENCE.md): Full endpoint specs, request/response models, status codes, and code examples.
- [**Testing & Benchmarks (`docs/TESTING_AND_BENCHMARKS.md`)**](docs/TESTING_AND_BENCHMARKS.md): Full test suite instructions, benchmark outputs, and compliance checklists.

---

## Quickstart

### 1. Prerequisites
- Python 3.11+
- `coinor-cbc` solver (included in Docker or via system package manager: `brew install cbc` on macOS, `apt install coinor-cbc` on Linux)

### 2. Environment Setup
```bash
# Clone and enter directory
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
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-...
FALLBACK_LLM_MODEL=gpt-4o-mini-backup
```
*(Note: If `LLM_API_KEY` is not provided, the service automatically utilizes the deterministic NLP fallback extractor.)*

### 4. Start Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
- API Docs: `http://localhost:8000/docs`
- Interactive Demo Dashboard: `http://localhost:8000/demo`
- Health Probe: `http://localhost:8000/health`

---

## Running the Automated Test Suite

```bash
# Run all unit, fuzz, guardrail, and sample pack integration tests
pytest -v

# Run the 10-case public sample benchmark report
python tests/generate_report.py
```

---

## Docker Deployment

```bash
# Build image
docker build -t gridwise-optimizer:v2 .

# Run container
docker run -d --name gridwise \
  -p 8000:8000 \
  -e PORT=8000 \
  -e LLM_API_KEY="sk-..." \
  gridwise-optimizer:v2
```

---

## Core Optimization Directives

| Directive Type | Description | Key Parameters |
| :--- | :--- | :--- |
| `solar_reduction` | Solar availability drops | `{"hours": [...], "factor": 0.0..1.0}` |
| `minimum_battery_reserve` | Emergency reserve floor | `{"hours": [...], "minimum_energy_kwh": float}` |
| `no_charge_window` | Charging is blocked | `{"hours": [...]}` |
| `no_discharge_window` | Discharging is blocked | `{"hours": [...]}` |
| `max_grid_window` | Feeder import limit | `{"hours": [...], "max_grid_kwh": float}` |
| `no_op` | Unrelated distractor note | `applies: false, structured_adjustment: null` |
