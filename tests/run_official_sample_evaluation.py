import json
import time
import requests
from fastapi.testclient import TestClient
from app.main import app

def run_evaluation():
    client = TestClient(app)
    
    with open("tests/sample_cases.json", "r") as f:
        pack = json.load(f)
        
    cases = pack["cases"]
    print("=" * 105)
    print(f"{'GRIDWISE OFFICIAL 10-SAMPLE EVALUATION AUDIT':^105}")
    print("=" * 105)
    
    results = []
    
    for case in cases:
        case_id = case["id"]
        label = case["label"]
        payload = case["input"]
        expected = case["expected_output"]
        
        t0 = time.time()
        response = client.post("/optimize-energy", json=payload)
        elapsed_ms = (time.time() - t0) * 1000
        
        if response.status_code != 200:
            results.append({
                "id": case_id,
                "label": label,
                "status": "FAIL",
                "reason": f"HTTP {response.status_code}: {response.text}",
                "elapsed_ms": elapsed_ms
            })
            continue
            
        data = response.json()
        
        # 1. Directive Interpretation
        dir_ok = True
        dir_details = []
        if len(data["directive_interpretation"]) != len(expected["directive_interpretation"]):
            dir_ok = False
            dir_details.append(f"Len mismatch ({len(data['directive_interpretation'])} vs {len(expected['directive_interpretation'])})")
        else:
            for act_d, exp_d in zip(data["directive_interpretation"], expected["directive_interpretation"]):
                if (act_d["directive_type"] != exp_d["directive_type"] or
                    act_d["applies"] != exp_d["applies"] or
                    act_d["structured_adjustment"] != exp_d["structured_adjustment"]):
                    dir_ok = False
                    dir_details.append(f"Note {act_d['note_index']}: got {act_d['directive_type']} (adj={act_d['structured_adjustment']}), exp {exp_d['directive_type']} (adj={exp_d['structured_adjustment']})")
                    
        # 2. Replay & Constraint verification
        plan = data["hourly_plan"]
        hours = payload["hours"]
        battery = payload["battery"]
        
        soc = battery["initial_energy_kwh"]
        constraints_ok = True
        constraint_violations = []
        
        calc_grid = 0.0
        calc_cost = 0.0
        calc_peak = 0.0
        
        # Apply solar adjustments if any
        eff_solar = [h["solar_kwh"] for h in hours]
        min_reserve = [battery["minimum_energy_kwh"]] * 24
        max_grid_cap = [float('inf')] * 24
        no_charge_hours = set()
        no_discharge_hours = set()
        
        for d in data["directive_interpretation"]:
            if not d["applies"] or not d["structured_adjustment"]:
                continue
            dtype = d["directive_type"]
            adj = d["structured_adjustment"]
            d_hours = adj.get("hours", [])
            if dtype == "solar_reduction":
                factor = adj.get("factor", 1.0)
                for h in d_hours:
                    eff_solar[h] = hours[h]["solar_kwh"] * factor
            elif dtype == "minimum_battery_reserve":
                res_kwh = adj.get("minimum_energy_kwh", battery["minimum_energy_kwh"])
                for h in d_hours:
                    min_reserve[h] = max(min_reserve[h], res_kwh)
            elif dtype == "max_grid_window":
                cap = adj.get("max_grid_kwh", float('inf'))
                for h in d_hours:
                    max_grid_cap[h] = min(max_grid_cap[h], cap)
            elif dtype == "no_charge_window":
                no_charge_hours.update(d_hours)
            elif dtype == "no_discharge_window":
                no_discharge_hours.update(d_hours)
                
        for h in range(24):
            p = plan[h]
            inp_h = hours[h]
            dem = inp_h["demand_kwh"]
            tar = inp_h["tariff_bdt_per_kwh"]
            
            g = p["grid_kwh"]
            s = p["solar_used_kwh"]
            act = p["battery_action"]
            b_kwh = p["battery_kwh"]
            b_after = p["battery_energy_after_kwh"]
            
            calc_grid += g
            calc_cost += g * tar
            calc_peak = max(calc_peak, g)
            
            # Solar limit
            if s > eff_solar[h] + 1e-4:
                constraints_ok = False
                constraint_violations.append(f"H{h}: solar {s} > eff_solar {eff_solar[h]}")
                
            # Rate limit
            if act == "charge":
                if b_kwh > battery["max_charge_kwh_per_hour"] + 1e-4:
                    constraints_ok = False
                    constraint_violations.append(f"H{h}: charge {b_kwh} > max_charge")
                if h in no_charge_hours and b_kwh > 1e-4:
                    constraints_ok = False
                    constraint_violations.append(f"H{h}: charged during no_charge_window")
                soc += b_kwh
            elif act == "discharge":
                if b_kwh > battery["max_discharge_kwh_per_hour"] + 1e-4:
                    constraints_ok = False
                    constraint_violations.append(f"H{h}: discharge {b_kwh} > max_discharge")
                if h in no_discharge_hours and b_kwh > 1e-4:
                    constraints_ok = False
                    constraint_violations.append(f"H{h}: discharged during no_discharge_window")
                soc -= b_kwh
            elif act == "idle":
                if b_kwh > 1e-4:
                    constraints_ok = False
                    constraint_violations.append(f"H{h}: idle but b_kwh={b_kwh}")
                    
            # SoC balance
            if abs(soc - b_after) > 0.05:
                constraints_ok = False
                constraint_violations.append(f"H{h}: SoC track mismatch {soc:.2f} vs {b_after:.2f}")
                
            # SoC limits
            if b_after < min_reserve[h] - 1e-4:
                constraints_ok = False
                constraint_violations.append(f"H{h}: SoC {b_after:.2f} < reserve {min_reserve[h]}")
            if b_after > battery["capacity_kwh"] + 1e-4:
                constraints_ok = False
                constraint_violations.append(f"H{h}: SoC {b_after:.2f} > capacity {battery['capacity_kwh']}")
                
            # Grid cap
            if g > max_grid_cap[h] + 1e-4:
                constraints_ok = False
                constraint_violations.append(f"H{h}: grid {g:.2f} > cap {max_grid_cap[h]}")
                
            # Power balance
            b_ch = b_kwh if act == "charge" else 0.0
            b_dis = b_kwh if act == "discharge" else 0.0
            lhs = g + s + b_dis
            rhs = dem + b_ch
            if abs(lhs - rhs) > 0.05:
                constraints_ok = False
                constraint_violations.append(f"H{h}: balance mismatch supply {lhs:.2f} != demand {rhs:.2f}")
                
        # Neutrality check
        if abs(soc - battery["initial_energy_kwh"]) > 0.05:
            constraints_ok = False
            constraint_violations.append(f"Neutrality failed: final {soc:.2f} != init {battery['initial_energy_kwh']}")
            
        # Cost optimality
        cost_diff = abs(data["total_cost_bdt"] - expected["total_cost_bdt"])
        grid_diff = abs(data["total_grid_kwh"] - expected["total_grid_kwh"])
        peak_diff = abs(data["peak_grid_kwh"] - expected["peak_grid_kwh"])
        
        opt_ok = (cost_diff < 0.05) and (grid_diff < 0.05) and (peak_diff < 0.05)
        
        results.append({
            "id": case_id,
            "label": label,
            "directives_ok": dir_ok,
            "directives_err": dir_details,
            "physics_ok": constraints_ok,
            "physics_err": constraint_violations,
            "cost_act": data["total_cost_bdt"],
            "cost_exp": expected["total_cost_bdt"],
            "grid_act": data["total_grid_kwh"],
            "grid_exp": expected["total_grid_kwh"],
            "peak_act": data["peak_grid_kwh"],
            "peak_exp": expected["peak_grid_kwh"],
            "cost_match": opt_ok,
            "elapsed_ms": elapsed_ms
        })

    # Print summary table
    print(f"{'Case ID':<10} | {'Scenario Label':<35} | {'Directives':<10} | {'Physics':<8} | {'Cost (BDT)':<14} | {'Exp Cost':<10} | {'Status':<6}")
    print("-" * 105)
    
    all_passed = True
    for r in results:
        status = "PASS" if (r["directives_ok"] and r["physics_ok"] and r["cost_match"]) else "FAIL"
        if status == "FAIL":
            all_passed = False
        dir_str = "MATCH" if r["directives_ok"] else "DIFF"
        phys_str = "VALID" if r["physics_ok"] else "VIOL"
        print(f"{r['id']:<10} | {r['label']:<35} | {dir_str:<10} | {phys_str:<8} | {r['cost_act']:<14.2f} | {r['cost_exp']:<10.2f} | {status:<6}")
        if r.get("directives_err"):
            print(f"   -> Directives: {r['directives_err']}")
        if r.get("physics_err"):
            print(f"   -> Physics: {r['physics_err']}")
            
    print("=" * 105)
    print(f"FINAL AUDIT RESULT: {'ALL 10 PUBLIC CASES 100% PERFECT & VERIFIED' if all_passed else 'SOME CASES FAILED'}")
    print("=" * 105)

if __name__ == "__main__":
    run_evaluation()
