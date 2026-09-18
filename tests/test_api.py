from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_optimize_energy_basic():
    hours = []
    for h in range(24):
        hours.append({
            "hour": h,
            "demand_kwh": 100.0,
            "solar_kwh": 0.0,
            "tariff_bdt_per_kwh": 10.0 if h < 18 else 20.0
        })
        
    payload = {
        "scenario_id": "test_scenario_1",
        "operator_notes": ["This is a test note"],
        "hours": hours,
        "battery": {
            "capacity_kwh": 500.0,
            "initial_energy_kwh": 200.0,
            "minimum_energy_kwh": 50.0,
            "max_charge_kwh_per_hour": 100.0,
            "max_discharge_kwh_per_hour": 100.0
        }
    }
    
    response = client.post("/optimize-energy", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["scenario_id"] == "test_scenario_1"
    assert len(data["hourly_plan"]) == 24
    assert len(data["directive_interpretation"]) == 1
    assert data["directive_interpretation"][0]["directive_type"] == "no_op"
    # Check end of day
    assert abs(data["hourly_plan"][-1]["battery_energy_after_kwh"] - 200.0) < 0.1
