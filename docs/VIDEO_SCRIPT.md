# GridWise — 3-Minute Solution & Architecture Video Script

This document provides a timed, slide-by-slide script for the 3-minute hackathon evaluation video (used for tie-breaking in scoring).

---

## Video Outline & Timing (Total: 3 minutes / 180 seconds)

```
00:00 - 00:20 (20s) | Slide 1: Challenge & Problem Context
00:20 - 00:50 (30s) | Slide 2: Decoupled 5-Stage Architecture
00:50 - 01:25 (35s) | Slide 3: LLM Interpretation & Guardrail Safety
01:25 - 02:00 (35s) | Slide 4: Mathematical Optimization & Peak Tie-Breaking
02:00 - 02:30 (30s) | Slide 5: Physical Replay Validation & 100% Benchmarks
02:30 - 03:00 (30s) | Slide 6: Production Readiness, Docker & Conclusion
```

---

## Detailed Narration Script

### [00:00 - 00:20] Slide 1: Challenge & Problem Context
> **Visual:** Title slide with team name, project title *"GridWise: LLM-Assisted Campus Energy Optimizer"*, and the core challenge statement.
>
> **Narration:**
> *"Hello, we are presenting GridWise, our production-grade energy optimization engine for the BUP CSE Fest 2026 Hackathon. The objective is to bridge natural language operator directives with 24-hour campus energy scheduling, minimizing grid electricity costs while strictly respecting physical battery, solar, and grid constraints."*

---

### [00:20 - 00:50] Slide 2: Decoupled 5-Stage Architecture
> **Visual:** Architecture flow diagram showing:
> Input $\to$ [1] LLM Interpreter $\to$ [2] Guardrail Validator $\to$ [3] PuLP LP Solver $\to$ [4] Replay Safety Layer $\to$ [5] API Output.
>
> **Narration:**
> *"To ensure absolute mathematical soundness, we implemented a decoupled 5-stage architecture. Untrusted natural language interpretation is strictly separated from the deterministic linear programming solver. A pure Python guardrail validator acts as a firewall between the LLM and the optimizer, followed by an independent physical replay engine before any response is served."*

---

### [00:50 - 01:25] Slide 3: LLM Interpretation & Guardrail Safety
> **Visual:** JSON snippet showing raw operator notes transformed into validated directive interpretations. Highlight in-memory cache and prompt context injection.
>
> **Narration:**
> *"In Stage 1, our LLM interpreter uses structured JSON schema generation and few-shot calibration to accurately parse complex, paraphrased shift notes into 6 standardized directive types. We inject battery capacity into the prompt context to resolve relative percentages like '50% reserve' into absolute kWh values. 
>
> An in-memory prompt cache eliminates repeated LLM latency, while dual-model failover and a deterministic NLP fallback guarantee zero-downtime resilience. Stage 2 validates key sets, time intervals, and physical bounds, safely downgrading any malformed outputs to no_op."*

---

### [01:25 - 02:00] Slide 4: Mathematical Optimization & Peak Tie-Breaking
> **Visual:** Optimization math equations (LP formulation, energy balance, SoC transition, and peak tie-breaker penalty).
>
> **Narration:**
> *"In Stage 3, we formulate the dispatch problem as a Linear Program using PuLP with the Coin-OR CBC solver. It models hourly energy balance, battery State of Charge transitions, charge and discharge rate ceilings, and end-of-day battery neutrality.
>
> To resolve dispatch ambiguity during equal-tariff hours, we introduced a negligible peak penalty term ($\epsilon = 10^{-5}$). This guarantees optimal cost minimization while automatically flattening grid demand peaks."*

---

### [02:00 - 02:30] Slide 5: Physical Replay Validation & 100% Benchmarks
> **Visual:** Terminal screen showing `pytest -v` passing all 23 tests and the 10/10 public sample benchmark table.
>
> **Narration:**
> *"Before responding, Stage 4 executes an independent physical replay check, verifying energy balance and battery neutrality across all 24 hours within a 0.01 tolerance. 
>
> Our test suite achieves 100% accuracy across all 10 official public sample cases, matching the expected optimal costs, total grid energy, and peak demand down to the penny."*

---

### [02:30 - 03:00] Slide 6: Production Readiness & Docker
> **Visual:** Docker run command, interactive `/demo` UI screenshot, and live API endpoints (`GET /health`, `POST /optimize-energy`).
>
> **Narration:**
> *"The service is containerized with Docker, binds dynamically to any port, includes sub-second response times, and features an interactive visual simulation dashboard at `/demo`. GridWise is robust, secure, mathematically sound, and ready for immediate deployment. Thank you!"*
