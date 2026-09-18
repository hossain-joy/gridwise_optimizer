# GridWise Testing & Benchmark Guide

## Test Suite Overview

The GridWise test suite provides comprehensive automated coverage across all layers of the service: API schema, LLM extraction & fallback, guardrails, linear programming optimization, and full-replay constraint validation.

```
tests/
├── sample_cases.json         # 10 Official Judge Sample Test Cases (v2.0)
├── test_sample_pack.py       # End-to-end API test verifying all 10 sample cases
├── test_directives.py        # Directive interpretation & NLP extraction unit tests
├── test_optimizer.py         # PuLP Linear Programming optimization unit tests
├── test_guardrail.py         # Guardrail boundary and downgrade security tests
├── test_fuzz.py              # Malformed payloads & 400 Bad Request verification
├── test_api.py               # Basic API health & endpoint sanity tests
├── verify_all.py             # Math & replay verification script
└── generate_report.py        # Benchmark report generator
```

---

## Running the Tests

### 1. Run Complete Test Suite
```bash
# Windows PowerShell
$env:PYTHONPATH="."
pytest -v

# Linux / macOS
PYTHONPATH=. pytest -v
```

### 2. Run Public Sample Benchmark Report
```bash
# Windows PowerShell
$env:PYTHONPATH="."
python tests/generate_report.py

# Linux / macOS
PYTHONPATH=. python tests/generate_report.py
```

---

## Benchmark Results (10/10 Sample Cases)

```
====================================================================================================
CASE ID    | LABEL                               | STATUS | DIRECTIVES | COST (ACT/EXP)     | GRID (ACT/EXP)     | PEAK (ACT/EXP)  
-----------------------------------------------------------------------------------------------------------------------------
SAMPLE-01  | Solar cleaning + distractor         | PASS   | MATCH      | 38365.00 / 38365.00 | 2692.50 / 2692.50  | 175.00 / 175.00 
SAMPLE-02  | Battery charging maintenance        | PASS   | MATCH      | 42885.00 / 42885.00 | 2915.00 / 2915.00  | 180.00 / 180.00 
SAMPLE-03  | Emergency reserve as percentage     | PASS   | MATCH      | 35480.00 / 35480.00 | 2430.00 / 2430.00  | 205.00 / 205.00 
SAMPLE-04  | No-discharge protection test        | PASS   | MATCH      | 40495.00 / 40495.00 | 2645.00 / 2645.00  | 225.00 / 225.00 
SAMPLE-05  | Temporary feeder grid cap           | PASS   | MATCH      | 33950.00 / 33950.00 | 2430.00 / 2430.00  | 175.00 / 175.00 
SAMPLE-06  | Multiple notes with distractor      | PASS   | MATCH      | 34090.00 / 34090.00 | 2395.00 / 2395.00  | 175.00 / 175.00 
SAMPLE-07  | Reserve plus transformer cap        | PASS   | MATCH      | 38550.00 / 38550.00 | 2560.00 / 2560.00  | 185.00 / 185.00 
SAMPLE-08  | Separate charge/discharge outages   | PASS   | MATCH      | 37665.00 / 37665.00 | 2490.00 / 2490.00  | 210.00 / 210.00 
SAMPLE-09  | Reduction wording normalization     | PASS   | MATCH      | 34873.00 / 34873.00 | 2504.00 / 2504.00  | 170.00 / 170.00 
SAMPLE-10  | Multi-constraint evening operation  | PASS   | MATCH      | 41620.00 / 41620.00 | 2715.00 / 2715.00  | 190.00 / 190.00 
====================================================================================================
```

---

## Evaluation Checklist Compliance

- [x] **Directive Count & Ordering:** Exactly one directive per operator note in identical `note_index` order.
- [x] **No-Op Semantics:** `applies: false` and `structured_adjustment: null`.
- [x] **Hourly Plan Length:** Exactly 24 entries from hour 0 to hour 23.
- [x] **Energy Balance:** $\text{grid}_h + \text{solar\_used}_h + \text{discharge}_h = \text{demand}_h + \text{charge}_h$ ($\text{TOL} \le 0.01$).
- [x] **Battery Limits:** $\text{active\_min\_reserve}_h \le \text{SoC}_h \le \text{capacity\_kwh}$.
- [x] **Charge / Discharge Windows:** Zero power dispatch during prohibited windows.
- [x] **Grid Import Caps:** $\text{grid}_h \le \text{max\_grid\_kwh}$ for all constrained hours.
- [x] **End-of-Day Neutrality:** $\text{SoC}_{23} = \text{initial\_energy\_kwh}$.
- [x] **Optimal Cost Minimization:** Match reference optimal cost within $0.01\text{ BDT}$.
- [x] **Deterministic Replay Safety:** Automatically replayed before returning 200 OK.
