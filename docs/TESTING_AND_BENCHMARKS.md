# GridWise Testing & Benchmark Guide

## Test Suite Overview

The GridWise test suite provides comprehensive automated coverage across all layers of the service: API schema, LLM extraction & fallback, guardrails, linear programming optimization, and full-replay constraint validation.

```
tests/
├── sample_cases.json         # 10 Official Judge Sample Test Cases (v2.0)
├── extended_cases.json       # 20 Additional Complex Synthetic Test Scenarios (SYNTH-11 to SYNTH-30)
├── test_all_30_cases.py      # Automated benchmark verifying all 30 scenarios (100% pass)
├── test_sample_pack.py       # End-to-end API test verifying official sample cases
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

### 1. Run Complete Pytest Suite (53 Tests)
```bash
# Windows PowerShell
$env:PYTHONPATH="."
pytest -v

# Linux / macOS
PYTHONPATH=. pytest -v
```

### 2. Run All 30 Cases Benchmark Runner
```bash
# Windows PowerShell
$env:PYTHONPATH="."
python tests/test_all_30_cases.py

# Linux / macOS
PYTHONPATH=. python tests/test_all_30_cases.py
```

---

## Comprehensive Benchmark Results (30/30 Cases — 100% Pass)

```
=========================================================================================================
CASE ID    | STATUS | COST (ACT / EXP)       | GRID (ACT / EXP)       | PEAK (ACT / EXP) | SCENARIO LABEL
---------------------------------------------------------------------------------------------------------
SAMPLE-01  | PASS   | 38365.00 / 38365.00    | 2692.50 / 2692.50      | 175.00 / 175.00  | Solar cleaning + distractor
SAMPLE-02  | PASS   | 42885.00 / 42885.00    | 2915.00 / 2915.00      | 180.00 / 180.00  | Battery charging maintenance
SAMPLE-03  | PASS   | 35480.00 / 35480.00    | 2430.00 / 2430.00      | 205.00 / 205.00  | Emergency reserve as percentage
SAMPLE-04  | PASS   | 40495.00 / 40495.00    | 2645.00 / 2645.00      | 225.00 / 225.00  | No-discharge protection test
SAMPLE-05  | PASS   | 33950.00 / 33950.00    | 2430.00 / 2430.00      | 175.00 / 175.00  | Temporary feeder grid cap
SAMPLE-06  | PASS   | 34090.00 / 34090.00    | 2395.00 / 2395.00      | 175.00 / 175.00  | Multiple notes with distractor
SAMPLE-07  | PASS   | 38550.00 / 38550.00    | 2560.00 / 2560.00      | 185.00 / 185.00  | Reserve plus transformer cap
SAMPLE-08  | PASS   | 37665.00 / 37665.00    | 2490.00 / 2490.00      | 210.00 / 210.00  | Separate charge/discharge outages
SAMPLE-09  | PASS   | 34873.00 / 34873.00    | 2504.00 / 2504.00      | 170.00 / 170.00  | Reduction wording normalization
SAMPLE-10  | PASS   | 41620.00 / 41620.00    | 2715.00 / 2715.00      | 190.00 / 190.00  | Multi-constraint evening operation
SYNTH-11   | PASS   | 38142.50 / 38142.50    | 2617.50 / 2617.50      | 193.75 / 193.75  | Overcast afternoon solar drop
SYNTH-12   | PASS   | 34355.00 / 34355.00    | 2325.00 / 2325.00      | 205.00 / 205.00  | Night relay upgrade no-discharge
SYNTH-13   | PASS   | 33975.00 / 33975.00    | 2325.00 / 2325.00      | 175.00 / 175.00  | Morning charger maintenance + distractor
SYNTH-14   | PASS   | 33305.00 / 33305.00    | 2325.00 / 2325.00      | 175.00 / 175.00  | Evening critical lab reserve percentage
SYNTH-15   | PASS   | 34005.00 / 34005.00    | 2325.00 / 2325.00      | 165.00 / 165.00  | Substation feeder constraint
SYNTH-16   | PASS   | 37798.00 / 37798.00    | 2563.00 / 2563.00      | 175.00 / 175.00  | Solar cleaning + charging outage + distractor
SYNTH-17   | PASS   | 39711.00 / 39711.00    | 2713.00 / 2713.00      | 198.00 / 198.00  | Dust storm severe solar drop
SYNTH-18   | PASS   | 34095.00 / 34095.00    | 2325.00 / 2325.00      | 175.00 / 175.00  | Morning charger isolation + evening grid limit
SYNTH-19   | PASS   | 34975.00 / 34975.00    | 2325.00 / 2325.00      | 205.00 / 205.00  | High emergency reserve + library distractor
SYNTH-20   | PASS   | 33980.00 / 33980.00    | 2325.00 / 2325.00      | 175.00 / 175.00  | Afternoon protection test no-discharge
SYNTH-21   | PASS   | 38199.00 / 38199.00    | 2604.00 / 2604.00      | 175.00 / 175.00  | Midday cloud cover reduction
SYNTH-22   | PASS   | 38724.00 / 38724.00    | 2631.00 / 2631.00      | 175.00 / 175.00  | Triple active constraints scenario
SYNTH-23   | PASS   | 39285.00 / 39285.00    | 2675.00 / 2675.00      | 175.00 / 175.00  | Midday inverter replacement complete outage
SYNTH-24   | PASS   | 34035.00 / 34035.00    | 2325.00 / 2325.00      | 175.00 / 175.00  | Midnight charger isolation
SYNTH-25   | PASS   | 34345.00 / 34345.00    | 2325.00 / 2325.00      | 205.00 / 205.00  | Critical server reserve with dual distractors
SYNTH-26   | PASS   | 33975.00 / 33975.00    | 2325.00 / 2325.00      | 175.00 / 175.00  | Military time evening transformer limit
SYNTH-27   | PASS   | 34035.00 / 34035.00    | 2325.00 / 2325.00      | 175.00 / 175.00  | Separate morning charge & evening discharge restrictions
SYNTH-28   | PASS   | 35975.00 / 35975.00    | 2325.00 / 2325.00      | 205.00 / 205.00  | High storm reserve percentage
SYNTH-29   | PASS   | 33975.00 / 33975.00    | 2325.00 / 2325.00      | 175.00 / 175.00  | Tight feeder limit + career distractor
SYNTH-30   | PASS   | 33975.00 / 33975.00    | 2325.00 / 2325.00      | 175.00 / 175.00  | All distractor notes scenario
=========================================================================================================
OVERALL RESULT: 30/30 CASES PASSED (100.0%)
=========================================================================================================
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
