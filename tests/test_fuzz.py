from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_missing_fields():
    payload = {
        "scenario_id": "test",
        # missing operator_notes
        "hours": [],
        "battery": {}
    }
    res = client.post("/optimize-energy", json=payload)
    assert res.status_code == 400

def test_invalid_hours_length():
    hours = []
    for h in range(23): # missing one hour
        hours.append({
            "hour": h,
            "demand_kwh": 100.0,
            "solar_kwh": 0.0,
            "tariff_bdt_per_kwh": 10.0
        })
    payload = {
        "scenario_id": "test",
        "operator_notes": ["Note 1"],
        "hours": hours,
        "battery": {
            "capacity_kwh": 500.0,
            "initial_energy_kwh": 200.0,
            "minimum_energy_kwh": 50.0,
            "max_charge_kwh_per_hour": 100.0,
            "max_discharge_kwh_per_hour": 100.0
        }
    }
    res = client.post("/optimize-energy", json=payload)
    assert res.status_code == 400

def test_battery_constraint_violation():
    hours = []
    for h in range(24):
        hours.append({
            "hour": h,
            "demand_kwh": 100.0,
            "solar_kwh": 0.0,
            "tariff_bdt_per_kwh": 10.0
        })
    payload = {
        "scenario_id": "test",
        "operator_notes": ["Note 1"],
        "hours": hours,
        "battery": {
            "capacity_kwh": 500.0,
            "initial_energy_kwh": 600.0, # invalid
            "minimum_energy_kwh": 50.0,
            "max_charge_kwh_per_hour": 100.0,
            "max_discharge_kwh_per_hour": 100.0
        }
    }
    res = client.post("/optimize-energy", json=payload)
    assert res.status_code == 400
