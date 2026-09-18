import json
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def load_all_cases():
    with open("tests/sample_cases.json", "r") as f:
        cases_10 = json.load(f)["cases"]
    with open("tests/extended_cases.json", "r") as f:
        cases_20 = json.load(f)["cases"]
    return cases_10 + cases_20

@pytest.mark.parametrize("case", load_all_cases(), ids=lambda c: c["id"])
def test_full_30_cases(case):
    scenario_id = case["id"]
    payload = case["input"]
    expected = case["expected_output"]

    response = client.post("/optimize-energy", json=payload)
    assert response.status_code == 200, f"API Error in {scenario_id}: {response.text}"
    data = response.json()

    # 1. Scenario ID
    assert data["scenario_id"] == scenario_id

    # 2. Directive Interpretation
    actual_dirs = data["directive_interpretation"]
    exp_dirs = expected["directive_interpretation"]
    assert len(actual_dirs) == len(exp_dirs)
    for ad, ed in zip(actual_dirs, exp_dirs):
        assert ad["note_index"] == ed["note_index"]
        assert ad["applies"] == ed["applies"]
        assert ad["directive_type"] == ed["directive_type"]
        assert ad["structured_adjustment"] == ed["structured_adjustment"]

    # 3. Hourly Plan
    plan = data["hourly_plan"]
    assert len(plan) == 24
    for h in range(24):
        p = plan[h]
        assert p["hour"] == h
        assert p["grid_kwh"] >= 0.0
        assert p["solar_used_kwh"] >= 0.0
        assert p["battery_action"] in ["idle", "charge", "discharge"]

    # 4. Totals (Tolerance 0.01)
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

if __name__ == "__main__":
    cases = load_all_cases()
    print("=" * 105)
    print(f"RUNNING ALL {len(cases)} TEST CASES (10 PUBLIC + 20 EXTENDED) VIA LIVE API")
    print("=" * 105)
    
    passed_count = 0
    for i, case in enumerate(cases, 1):
        cid = case["id"]
        label = case["label"]
        payload = case["input"]
        expected = case["expected_output"]
        
        res = client.post("/optimize-energy", json=payload)
        data = res.json()
        
        cost_ok = abs(data["total_cost_bdt"] - expected["total_cost_bdt"]) < 0.01
        grid_ok = abs(data["total_grid_kwh"] - expected["total_grid_kwh"]) < 0.01
        peak_ok = abs(data["peak_grid_kwh"] - expected["peak_grid_kwh"]) < 0.01
        
        dirs_ok = True
        for ad, ed in zip(data.get("directive_interpretation", []), expected["directive_interpretation"]):
            if (ad["directive_type"] != ed["directive_type"] or
                ad["applies"] != ed["applies"] or
                ad["structured_adjustment"] != ed["structured_adjustment"]):
                dirs_ok = False
                break
                
        all_ok = (res.status_code == 200 and cost_ok and grid_ok and peak_ok and dirs_ok)
        if all_ok:
            passed_count += 1
            
        status = "PASS" if all_ok else "FAIL"
        cost_str = f"{data.get('total_cost_bdt', 0):.2f}/{expected['total_cost_bdt']:.2f}"
        grid_str = f"{data.get('total_grid_kwh', 0):.2f}/{expected['total_grid_kwh']:.2f}"
        peak_str = f"{data.get('peak_grid_kwh', 0):.2f}/{expected['peak_grid_kwh']:.2f}"
        print(f"[{i:02d}/30] {cid:<10} | {status:<5} | Cost: {cost_str:<18} | Grid: {grid_str:<18} | Peak: {peak_str:<15} | {label}")
        
    print("=" * 105)
    print(f"OVERALL RESULT: {passed_count}/{len(cases)} CASES PASSED ({passed_count/len(cases)*100:.1f}%)")
    print("=" * 105)
