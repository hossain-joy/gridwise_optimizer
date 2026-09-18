# GridWise Energy Optimizer — System Architecture

## Overview

GridWise Energy Optimizer is a high-reliability, microservice-based optimization engine designed for the BUP CSE Fest Hackathon. It bridges untrusted natural language operational directives with deterministic linear programming to compute optimal 24-hour campus energy dispatch schedules.

<p align="center">
  <img src="architecture.png" alt="GridWise Architecture Diagram" width="850">
</p>

---

## The 5-Stage Pipeline

### Stage 1: LLM Interpreter & In-Memory Cache
- **Goal:** Extract semantic directives from unstructured shift operator notes.
- **Normalization & Caching:** Notes are normalized (`lowercase`, punctuation stripped, whitespace collapsed). Identical requests bypass LLM inference entirely (0ms latency).
- **Context Injection:** The prompt provides `Battery Capacity` along with operator notes, enabling the interpreter to translate relative requirements (e.g., *"keep 50% reserve"*) into absolute quantities (`100 kWh`).
- **Resilience Strategy:**
  1. *Primary LLM* with strict JSON mode and few-shot calibration.
  2. *Secondary Fallback LLM* if primary times out or returns malformed data.
  3. *Deterministic Rule-Based NLP Extractor* for zero-downtime offline execution.
  4. Safe fallback to `no_op` if extraction fails.

---

### Stage 2: Guardrail Validator
- **Goal:** Protect mathematical solver from hallucinated or unsafe parameters.
- **Rules Enforced:**
  - **Type & Key Rigidity:** `structured_adjustment` dictionaries must contain *only* the authorized keys for that directive type (extra keys trigger immediate downgrade to `no_op`).
  - **Time Window Correctness:** Must be unique integers in `0..23` sorted in ascending order.
  - **Value Boundaries:**
    - `solar_reduction`: `0.0 <= factor <= 1.0`
    - `minimum_battery_reserve`: `0.0 <= minimum_energy_kwh <= battery.capacity_kwh`
    - `max_grid_window`: `max_grid_kwh >= 0.0`
  - **Directive Application Rules:**
    - `no_op` must have `applies=False` and `structured_adjustment=null`.
    - Active directives must have `applies=True`.

---

### Stage 3: Mathematical Optimizer (Linear Programming)
- **Goal:** Compute the mathematically provable minimum cost energy dispatch schedule over a 24-hour horizon ($h \in \{0, \dots, 23\}$).
- **Formulation:**

$$\min \sum_{h=0}^{23} \left( \text{grid}_h \cdot \text{tariff}_h \right) + 10^{-5} \cdot \text{peak\_grid}$$

**Subject to:**

1. **Energy Balance ($h = 0 \dots 23$):**
   $$\text{grid}_h + \text{solar\_used}_h + \text{discharge}_h = \text{demand}_h + \text{charge}_h$$

2. **Solar Bounds ($h = 0 \dots 23$):**
   $$0 \le \text{solar\_used}_h \le \text{effective\_solar}_h$$

3. **Battery State of Charge Transition ($h = 0 \dots 23$):**
   $$\text{SoC}_h = \text{SoC}_{h-1} + \text{charge}_h - \text{discharge}_h \quad (\text{where } \text{SoC}_{-1} = \text{initial\_energy})$$

4. **Battery Energy Bounds ($h = 0 \dots 23$):**
   $$\text{active\_min\_reserve}_h \le \text{SoC}_h \le \text{capacity}$$

5. **Charge & Discharge Rate Limits ($h = 0 \dots 23$):**
   $$0 \le \text{charge}_h \le (\text{max\_charge} \text{ if } \text{can\_charge}_h \text{ else } 0)$$
   $$0 \le \text{discharge}_h \le (\text{max\_discharge} \text{ if } \text{can\_discharge}_h \text{ else } 0)$$

6. **Grid Import Limit ($h = 0 \dots 23$):**
   $$0 \le \text{grid}_h \le \text{active\_max\_grid}_h$$

7. **End-of-Day Neutrality:**
   $$\text{SoC}_{23} = \text{initial\_energy}$$

8. **Peak Grid Tracking:**
   $$\text{peak\_grid} \ge \text{grid}_h \quad \forall h \in \{0 \dots 23\}$$

---

### Stage 4: Replay & Energy Balance Safety Layer
- **Goal:** Guarantee schedule integrity before dispatching to the client.
- **Replay Verification:**
  - Independently validates energy conservation per hour ($|\text{supply} - \text{demand}| \le 0.01$).
  - Re-computes $\text{total\_grid\_kwh}$, $\text{total\_cost\_bdt}$, and $\text{peak\_grid\_kwh}$ from raw hourly plans.
  - Verifies battery energy neutrality ($|\text{SoC}_{23} - \text{initial\_energy}| \le 0.01$).

---

### Stage 5: Response Serialization
- Produces clean JSON output matching the official schema.
- Retains `null` for `no_op` structured adjustments while omitting extraneous keys.
