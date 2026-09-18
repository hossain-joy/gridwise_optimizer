# GridWise API Reference

## Base Endpoints

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Liveness & readiness probe |
| `GET` | `/demo` | Interactive visual dashboard for real-time scenario simulation |
| `POST` | `/optimize-energy` | Main 24-hour LLM-assisted energy schedule optimization |

---

## POST `/optimize-energy`

Accepts scenario parameters, 24-hour forecasts, battery characteristics, and natural language operator notes. Returns validated directive interpretations and the optimal cost-minimizing hourly schedule.

### Request Body Schema (`OptimizeRequest`)

| Field | Type | Required | Description |
| :--- | :--- | :---: | :--- |
| `scenario_id` | `string` | **Yes** | Unique identifier for the scenario (non-empty). |
| `operator_notes` | `List[string]` | **Yes** | 1 to 3 non-empty natural language strings from operators. |
| `hours` | `List[HourInput]` | **Yes** | Exactly 24 unique entries corresponding to hours `0` through `23`. |
| `battery` | `BatteryInput` | **Yes** | Physical battery specifications and initial state. |

#### `HourInput` Schema
```json
{
  "hour": 0,
  "demand_kwh": 90.0,
  "solar_kwh": 0.0,
  "tariff_bdt_per_kwh": 6.0
}
```

#### `BatteryInput` Schema
```json
{
  "capacity_kwh": 220.0,
  "initial_energy_kwh": 110.0,
  "minimum_energy_kwh": 40.0,
  "max_charge_kwh_per_hour": 50.0,
  "max_discharge_kwh_per_hour": 50.0
}
```

---

### Response Body Schema (`OptimizeResponse`)

```json
{
  "scenario_id": "SAMPLE-01",
  "directive_interpretation": [
    {
      "note_index": 0,
      "applies": true,
      "directive_type": "solar_reduction",
      "structured_adjustment": {
        "hours": [12, 13],
        "factor": 0.25
      },
      "explanation": "Solar availability reduced to factor 0.25 during specified window."
    },
    {
      "note_index": 1,
      "applies": false,
      "directive_type": "no_op",
      "structured_adjustment": null,
      "explanation": "This note does not affect today's 24-hour energy schedule."
    }
  ],
  "hourly_plan": [
    {
      "hour": 0,
      "grid_kwh": 90.0,
      "solar_used_kwh": 0.0,
      "battery_action": "idle",
      "battery_kwh": 0.0,
      "battery_energy_after_kwh": 110.0
    }
  ],
  "total_grid_kwh": 2692.5,
  "total_cost_bdt": 38365.0,
  "peak_grid_kwh": 175.0,
  "plan_summary": "Optimal schedule computed adhering to 1 directive(s): solar_reduction."
}
```

---

## Status Codes & Error Handling

| HTTP Status | Reason | Payload |
| :---: | :--- | :--- |
| `200 OK` | Optimization successful | Full `OptimizeResponse` JSON |
| `400 Bad Request` | Structural schema validation failure (e.g. invalid hour count, empty note, negative capacity) | `{"detail": [...]}` |
| `500 Internal Error` | Optimization or Replay failure | `{"detail": "Optimizer produced invalid schedule: ..."}` |

---

## Code Examples

### 1. cURL
```bash
curl -X POST http://localhost:8000/optimize-energy \
  -H "Content-Type: application/json" \
  -d @sample_request.json
```

### 2. Python (`httpx`)
```python
import httpx

payload = {
    "scenario_id": "SAMPLE-01",
    "operator_notes": [
        "Facilities will wash the rooftop solar panels from noon until 2 PM. During cleaning, usable solar should be treated as roughly 25% of the forecast.",
        "The sports office moved next month's registration deadline."
    ],
    "hours": [...],  # 24 hour objects
    "battery": {
        "capacity_kwh": 220,
        "initial_energy_kwh": 110,
        "minimum_energy_kwh": 40,
        "max_charge_kwh_per_hour": 50,
        "max_discharge_kwh_per_hour": 50
    }
}

response = httpx.post("http://localhost:8000/optimize-energy", json=payload)
data = response.json()
print("Total Cost (BDT):", data["total_cost_bdt"])
print("Total Grid (kWh):", data["total_grid_kwh"])
```

### 3. JavaScript (`fetch`)
```javascript
const response = await fetch("http://localhost:8000/optimize-energy", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(payload)
});
const data = await response.json();
console.log(`Optimal Cost: ${data.total_cost_bdt} BDT`);
```
