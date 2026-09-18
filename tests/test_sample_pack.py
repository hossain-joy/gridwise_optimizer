import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.replay import validate_replay

client = TestClient(app)

def load_sample_cases():
    with open("tests/sample_cases.json", "r") as f:
        data = json.load(f)
    return data["cases"]

@pytest.mark.parametrize("case", load_sample_cases(), ids=lambda c: c["id"])
def test_sample_case_end_to_end_api(case):
    scenario_id = case["id"]
    payload = case["input"]
    expected = case["expected_output"]
    
    # 1. Hit the POST /optimize-energy endpoint
    response = client.post("/optimize-energy", json=payload)
    assert response.status_code == 200, f"API error: {response.text}"
    data = response.json()
    
    # 2. Check scenario_id
    assert data["scenario_id"] == scenario_id
    
    # 3. Check directive interpretations
    assert len(data["directive_interpretation"]) == len(expected["directive_interpretation"])
    for actual_d, exp_d in zip(data["directive_interpretation"], expected["directive_interpretation"]):
        assert actual_d["note_index"] == exp_d["note_index"]
        assert actual_d["applies"] == exp_d["applies"]
        assert actual_d["directive_type"] == exp_d["directive_type"]
        assert actual_d["structured_adjustment"] == exp_d["structured_adjustment"]
        assert isinstance(actual_d["explanation"], str) and len(actual_d["explanation"]) > 0

    # 4. Check hourly plan size & fields
    hourly_plan = data["hourly_plan"]
    assert len(hourly_plan) == 24
    for h in range(24):
        p = hourly_plan[h]
        assert p["hour"] == h
        assert p["grid_kwh"] >= 0.0
        assert p["solar_used_kwh"] >= 0.0
        assert p["battery_action"] in ["idle", "charge", "discharge"]
        assert p["battery_kwh"] >= 0.0
        assert p["battery_energy_after_kwh"] >= 0.0

    # 5. Check optimal cost and grid totals against reference (tolerance 0.01)
    TOL = 0.01
    assert abs(data["total_cost_bdt"] - expected["total_cost_bdt"]) < TOL, (
        f"Cost mismatch: got {data['total_cost_bdt']}, expected {expected['total_cost_bdt']}"
    )
    assert abs(data["total_grid_kwh"] - expected["total_grid_kwh"]) < TOL, (
        f"Grid mismatch: got {data['total_grid_kwh']}, expected {expected['total_grid_kwh']}"
    )
    assert abs(data["peak_grid_kwh"] - expected["peak_grid_kwh"]) < TOL, (
        f"Peak mismatch: got {data['peak_grid_kwh']}, expected {expected['peak_grid_kwh']}"
    )

    # 6. Check summary
    assert isinstance(data["plan_summary"], str) and len(data["plan_summary"]) > 0
