# GridWise Directive Specification & Interpretation Rules

This document details the exact semantics, expected JSON schema, and time normalization rules for the 6 directive types recognized by the GridWise LLM Energy Optimizer.

---

## 1. Directive Types & Required Schemas

### 1.1 `solar_reduction`
- **Description:** Rooftop solar generation is reduced due to scheduled maintenance, panel washing, inverter constraints, or weather conditions.
- **`applies`:** `true`
- **`structured_adjustment` Shape:**
  ```json
  {
    "hours": [12, 13],
    "factor": 0.25
  }
  ```
- **Semantic Rules:**
  - `factor` represents the **usable fraction remaining** ($0.0 \le \text{factor} \le 1.0$).
  - *"An 80% reduction"* $\implies \text{factor} = 1.0 - 0.80 = 0.20$.
  - *"Usable solar should be treated as roughly 25%"* $\implies \text{factor} = 0.25$.
  - *"Leave about half of the forecast output"* $\implies \text{factor} = 0.50$.
  - Effective solar per listed hour becomes: $\text{solar\_effective}_h = \text{solar\_base}_h \cdot \text{factor}$.

---

### 1.2 `minimum_battery_reserve`
- **Description:** Battery State of Charge (SoC) must stay at or above a higher threshold for emergency operations, critical load readiness, or hospital/data center backup.
- **`applies`:** `true`
- **`structured_adjustment` Shape:**
  ```json
  {
    "hours": [18, 19, 20],
    "minimum_energy_kwh": 100.0
  }
  ```
- **Semantic Rules:**
  - `minimum_energy_kwh` is an absolute energy amount ($0 \le \text{minimum\_energy\_kwh} \le \text{capacity\_kwh}$).
  - Percentage-based requirements must be translated using the scenario's battery capacity:
    - Example: *"Keep at least 50% of the battery capacity in reserve"* with a $200\text{ kWh}$ battery $\implies \text{minimum\_energy\_kwh} = 100.0$.
  - Raises the lower bound of battery energy for each hour $h \in \text{hours}$: $\text{SoC}_h \ge \text{minimum\_energy\_kwh}$.

---

### 1.3 `no_charge_window`
- **Description:** Battery charging is prohibited (e.g., charger offline, electrical maintenance, or circuit testing).
- **`applies`:** `true`
- **`structured_adjustment` Shape:**
  ```json
  {
    "hours": [2, 3, 4]
  }
  ```
- **Semantic Rules:**
  - Enforces $\text{charge}_h = 0.0$ for all $h \in \text{hours}$.
  - The battery can still idle or discharge normally during this window.

---

### 1.4 `no_discharge_window`
- **Description:** Battery discharging is prohibited (e.g., relay protection testing, inverter inspection).
- **`applies`:** `true`
- **`structured_adjustment` Shape:**
  ```json
  {
    "hours": [18, 19]
  }
  ```
- **Semantic Rules:**
  - Enforces $\text{discharge}_h = 0.0$ for all $h \in \text{hours}$.
  - The battery can still idle or charge normally during this window.

---

### 1.5 `max_grid_window`
- **Description:** Grid import from the substation/feeder is capped to a maximum allowed rate.
- **`applies`:** `true`
- **`structured_adjustment` Shape:**
  ```json
  {
    "hours": [18, 19, 20],
    "max_grid_kwh": 155.0
  }
  ```
- **Semantic Rules:**
  - Caps grid power: $\text{grid}_h \le \text{max\_grid\_kwh}$ for all $h \in \text{hours}$.
  - Requires the optimizer to discharge battery or schedule charging ahead of time to satisfy demand.

---

### 1.6 `no_op`
- **Description:** Unrelated announcements, non-energy operational notices, cafeteria menus, room bookings, or deadline changes.
- **`applies`:** `false`
- **`structured_adjustment` Shape:** `null`
- **Semantic Rules:**
  - Must have `applies: false` and `structured_adjustment: null`.
  - Has zero effect on energy schedules, demands, or battery limits.

---

## 2. Time Window Formatting Rules

| Textual Phrase | Start Hour (Inclusive) | End Hour (Exclusive) | Array Representation (`hours`) |
| :--- | :---: | :---: | :--- |
| `"from noon until 2 PM"` | 12 | 14 | `[12, 13]` |
| `"from 2 AM until 5 AM"` | 2 | 5 | `[2, 3, 4]` |
| `"from 6 PM until 9 PM"` | 18 | 21 | `[18, 19, 20]` |
| `"from 6 PM until 8 PM"` | 18 | 20 | `[18, 19]` |
| `"from 10 AM until noon"` | 10 | 12 | `[10, 11]` |
| `"between 11 AM and 2 PM"` | 11 | 14 | `[11, 12, 13]` |
| `"from 7 PM until 10 PM"` | 19 | 22 | `[19, 20, 21]` |
| `"13:00 to 15:00"` | 13 | 15 | `[13, 14]` |
| `"midnight to 2am"` | 0 | 2 | `[0, 1]` |

- **Start-Inclusive, End-Exclusive:** A window of *"1 PM to 3 PM"* spans 13:00 to 15:00, which includes hour 13 and hour 14, mapping strictly to `[13, 14]`.
- **Ordering & Uniqueness:** The `hours` array must be sorted in ascending order and contain only unique integers from $0$ to $23$.
