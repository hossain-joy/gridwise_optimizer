import json
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def run_report():
    with open("tests/sample_cases.json") as f:
        data = json.load(f)

    cases = data["cases"]
    print("=" * 100)
    print("GRIDWISE OPTIMIZATION TEST REPORT — 10 PUBLIC SAMPLE CASES")
    print("=" * 100)

    summary_rows = []

    for case in cases:
        cid = case["id"]
        label = case["label"]
        payload = case["input"]
        expected = case["expected_output"]

        # Call FastAPI POST /optimize-energy
        response = client.post("/optimize-energy", json=payload)
        status_code = response.status_code
        data = response.json()

        # Directive match check
        dir_match = True
        actual_dirs = data.get("directive_interpretation", [])
        exp_dirs = expected["directive_interpretation"]
        if len(actual_dirs) != len(exp_dirs):
            dir_match = False
        else:
            for ad, ed in zip(actual_dirs, exp_dirs):
                if (ad["directive_type"] != ed["directive_type"] or
                    ad["applies"] != ed["applies"] or
                    ad["structured_adjustment"] != ed["structured_adjustment"]):
                    dir_match = False
                    break

        actual_cost = data.get("total_cost_bdt", 0)
        exp_cost = expected["total_cost_bdt"]
        actual_grid = data.get("total_grid_kwh", 0)
        exp_grid = expected["total_grid_kwh"]
        actual_peak = data.get("peak_grid_kwh", 0)
        exp_peak = expected["peak_grid_kwh"]

        cost_match = abs(actual_cost - exp_cost) < 0.01
        grid_match = abs(actual_grid - exp_grid) < 0.01
        peak_match = abs(actual_peak - exp_peak) < 0.01

        all_ok = (status_code == 200 and dir_match and cost_match and grid_match and peak_match)

        summary_rows.append({
            "id": cid,
            "label": label,
            "status": "PASS" if all_ok else "FAIL",
            "directives": "MATCH" if dir_match else "MISMATCH",
            "cost": f"{actual_cost:.2f} / {exp_cost:.2f}",
            "grid": f"{actual_grid:.2f} / {exp_grid:.2f}",
            "peak": f"{actual_peak:.2f} / {exp_peak:.2f}",
        })

        print(f"\n[{cid}] {label}")
        print(f"  Notes ({len(payload['operator_notes'])}):")
        for i, n in enumerate(payload["operator_notes"]):
            print(f"    - Note {i}: \"{n}\"")
        print(f"  Directives Extracted ({len(actual_dirs)}):")
        for d in actual_dirs:
            print(f"    - Note {d['note_index']}: applies={d['applies']}, type={d['directive_type']}, adj={d['structured_adjustment']}")
        print(f"  Metrics:")
        print(f"    - Total Cost (BDT): {actual_cost:.2f} (Expected: {exp_cost:.2f}) -> {'OK' if cost_match else 'FAIL'}")
        print(f"    - Total Grid (kWh): {actual_grid:.2f} (Expected: {exp_grid:.2f}) -> {'OK' if grid_match else 'FAIL'}")
        print(f"    - Peak Grid  (kWh): {actual_peak:.2f} (Expected: {exp_peak:.2f}) -> {'OK' if peak_match else 'FAIL'}")
        print(f"  Result: {'PASS' if all_ok else 'FAIL'}")

    print("\n" + "=" * 100)
    print(f"{'CASE ID':<10} | {'LABEL':<35} | {'STATUS':<6} | {'DIRECTIVES':<10} | {'COST (ACT/EXP)':<18} | {'GRID (ACT/EXP)':<18} | {'PEAK (ACT/EXP)':<16}")
    print("-" * 125)
    for r in summary_rows:
        print(f"{r['id']:<10} | {r['label']:<35} | {r['status']:<6} | {r['directives']:<10} | {r['cost']:<18} | {r['grid']:<18} | {r['peak']:<16}")
    print("=" * 100)

if __name__ == "__main__":
    run_report()
