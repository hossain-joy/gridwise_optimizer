import json
import pulp
from app.models import OptimizeRequest
from app.guardrail import apply_directives, validate_directive

def run():
    with open("tests/sample_cases.json") as f:
        cases = json.load(f)["cases"]

    all_passed = True
    print(f"{'CASE ID':<12} | {'STATUS':<6} | {'TOTAL COST (BDT)':<22} | {'TOTAL GRID (kWh)':<22} | {'PEAK GRID (kWh)':<20}")
    print("-" * 90)

    for case in cases:
        cid = case["id"]
        req = OptimizeRequest(**case["input"])
        expected = case["expected_output"]
        directives = [
            validate_directive(raw, len(req.operator_notes), req.battery.capacity_kwh, cid)
            for raw in expected["directive_interpretation"]
        ]
        demand, solar, tariff, active_min_reserve, active_max_grid, can_charge, can_discharge = apply_directives(req, directives)
        battery = req.battery.model_dump()

        prob = pulp.LpProblem(f"TestPeak_{cid}", pulp.LpMinimize)
        grid_vars = []
        solar_used_vars = []
        charge_vars = []
        discharge_vars = []
        battery_energy_vars = []
        peak_var = pulp.LpVariable("peak", lowBound=0)

        for h in range(24):
            ub_grid = active_max_grid[h] if active_max_grid[h] != float("inf") else None
            grid_vars.append(pulp.LpVariable(f"g_{h}", lowBound=0, upBound=ub_grid))
            solar_used_vars.append(pulp.LpVariable(f"s_{h}", lowBound=0, upBound=solar[h]))
            ub_c = battery["max_charge_kwh_per_hour"] if can_charge[h] else 0.0
            charge_vars.append(pulp.LpVariable(f"c_{h}", lowBound=0, upBound=ub_c))
            ub_d = battery["max_discharge_kwh_per_hour"] if can_discharge[h] else 0.0
            discharge_vars.append(pulp.LpVariable(f"d_{h}", lowBound=0, upBound=ub_d))
            battery_energy_vars.append(pulp.LpVariable(f"b_{h}", lowBound=active_min_reserve[h], upBound=battery["capacity_kwh"]))

        for h in range(24):
            prob += grid_vars[h] + solar_used_vars[h] + discharge_vars[h] == demand[h] + charge_vars[h]
            prev_b = battery_energy_vars[h-1] if h > 0 else battery["initial_energy_kwh"]
            prob += battery_energy_vars[h] == prev_b + charge_vars[h] - discharge_vars[h]
            prob += peak_var >= grid_vars[h]

        prob += battery_energy_vars[23] == battery["initial_energy_kwh"]
        # Objective: minimize total cost + tiny peak penalty for tie-breaking
        prob += pulp.lpSum([grid_vars[h] * tariff[h] for h in range(24)]) + 1e-5 * peak_var
        prob.solve(pulp.PULP_CBC_CMD(msg=False))

        cost = round(sum((grid_vars[h].varValue or 0) * tariff[h] for h in range(24)), 4)
        grid_tot = round(sum((grid_vars[h].varValue or 0) for h in range(24)), 4)
        peak = round(max(grid_vars[h].varValue or 0 for h in range(24)), 4)

        cost_diff = abs(cost - expected["total_cost_bdt"])
        grid_diff = abs(grid_tot - expected["total_grid_kwh"])
        peak_diff = abs(peak - expected["peak_grid_kwh"])
        passed = (cost_diff < 0.01 and grid_diff < 0.01 and peak_diff < 0.01)
        if not passed:
            all_passed = False

        status_str = "PASS" if passed else "FAIL"
        cost_str = f"{cost:.1f} (exp {expected['total_cost_bdt']:.1f})"
        grid_str = f"{grid_tot:.1f} (exp {expected['total_grid_kwh']:.1f})"
        peak_str = f"{peak:.1f} (exp {expected['peak_grid_kwh']:.1f})"
        print(f"{cid:<12} | {status_str:<6} | {cost_str:<22} | {grid_str:<22} | {peak_str:<20}")

    print("-" * 90)
    print("ALL 10 SAMPLE CASES RESULT:", "ALL PASSED" if all_passed else "SOME FAILED")

if __name__ == "__main__":
    run()
