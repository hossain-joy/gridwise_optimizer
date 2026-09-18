import pulp
import logging
from typing import List, Tuple
from .models import HourlyPlan

logger = logging.getLogger(__name__)

def run_optimizer(
    demand: List[float],
    solar: List[float],
    tariff: List[float],
    battery: dict,
    active_min_reserve: List[float],
    active_max_grid: List[float],
    can_charge: List[bool],
    can_discharge: List[bool],
) -> Tuple[List[HourlyPlan], float, float, float]:
    """
    Runs the LP optimizer to find the cost-minimal 24-hour battery schedule.
    Returns: (hourly_plan_list, total_grid_kwh, total_cost_bdt, peak_grid_kwh)
    """
    prob = pulp.LpProblem("GridWise_Optimization", pulp.LpMinimize)
    
    # Decision variables
    grid_vars = []
    solar_used_vars = []
    charge_vars = []
    discharge_vars = []
    battery_energy_vars = []
    
    for h in range(24):
        # Grid bounds
        ub_grid = active_max_grid[h] if active_max_grid[h] != float('inf') else None
        grid_vars.append(pulp.LpVariable(f"grid_{h}", lowBound=0, upBound=ub_grid))
        
        # Solar bounds
        solar_used_vars.append(pulp.LpVariable(f"solar_used_{h}", lowBound=0, upBound=solar[h]))
        
        # Charge bounds
        ub_charge = battery["max_charge_kwh_per_hour"] if can_charge[h] else 0.0
        charge_vars.append(pulp.LpVariable(f"charge_{h}", lowBound=0, upBound=ub_charge))
        
        # Discharge bounds
        ub_discharge = battery["max_discharge_kwh_per_hour"] if can_discharge[h] else 0.0
        discharge_vars.append(pulp.LpVariable(f"discharge_{h}", lowBound=0, upBound=ub_discharge))
        
        # Battery state
        # The bounds can be set on the variable directly or via constraints.
        battery_energy_vars.append(
            pulp.LpVariable(f"battery_energy_{h}", lowBound=active_min_reserve[h], upBound=battery["capacity_kwh"])
        )

    # Peak grid variable for secondary tie-breaking (minimizing peak grid among cost-equivalent optimal solutions)
    peak_var = pulp.LpVariable("peak_grid_var", lowBound=0)
    for h in range(24):
        prob += peak_var >= grid_vars[h]

    # Objective: minimize total cost with a negligible peak penalty tie-breaker (1e-5)
    prob += pulp.lpSum([grid_vars[h] * tariff[h] for h in range(24)]) + 1e-5 * peak_var
    
    # Constraints
    for h in range(24):
        # Energy balance
        prob += grid_vars[h] + solar_used_vars[h] + discharge_vars[h] == demand[h] + charge_vars[h], f"Energy_Balance_{h}"
        
        # Battery state transition
        prev_energy = battery_energy_vars[h-1] if h > 0 else battery["initial_energy_kwh"]
        prob += battery_energy_vars[h] == prev_energy + charge_vars[h] - discharge_vars[h], f"Battery_Transition_{h}"
    
    # Terminal constraint: end-of-day neutrality
    prob += battery_energy_vars[23] == battery["initial_energy_kwh"], "End_of_day_neutrality"
    
    # Solve
    solver = pulp.PULP_CBC_CMD(msg=False)
    prob.solve(solver)
    
    if pulp.LpStatus[prob.status] != 'Optimal':
        # Log and raise an explicit error; the caller should map this to a 422 or 500
        logger.error(f"Solver failed. Status: {pulp.LpStatus[prob.status]}")
        raise ValueError(f"Infeasible scenario or solver failed. Status: {pulp.LpStatus[prob.status]}")
        
    # Extract results
    hourly_plans = []
    total_grid_kwh = 0.0
    total_cost_bdt = 0.0
    peak_grid_kwh = 0.0
    
    for h in range(24):
        g_val = grid_vars[h].varValue or 0.0
        s_val = solar_used_vars[h].varValue or 0.0
        c_val = charge_vars[h].varValue or 0.0
        d_val = discharge_vars[h].varValue or 0.0
        b_val = battery_energy_vars[h].varValue or 0.0
        
        # Handle numerical noise (below 1e-6 -> 0)
        if c_val < 1e-6: c_val = 0.0
        if d_val < 1e-6: d_val = 0.0
        if s_val < 1e-6: s_val = 0.0
        if g_val < 1e-6: g_val = 0.0
        
        if c_val > 0 and d_val > 0:
            # Both shouldn't be active at the same time in optimal solution. Net them out.
            if c_val > d_val:
                c_val -= d_val
                d_val = 0.0
            else:
                d_val -= c_val
                c_val = 0.0
                
        # Determine battery action
        if c_val > 0:
            battery_action = "charge"
            battery_kwh = c_val
        elif d_val > 0:
            battery_action = "discharge"
            battery_kwh = d_val
        else:
            battery_action = "idle"
            battery_kwh = 0.0
            
        hourly_plans.append(HourlyPlan(
            hour=h,
            grid_kwh=round(g_val, 4),
            solar_used_kwh=round(s_val, 4),
            battery_action=battery_action,
            battery_kwh=round(battery_kwh, 4),
            battery_energy_after_kwh=round(b_val, 4)
        ))
        
        total_grid_kwh += g_val
        total_cost_bdt += g_val * tariff[h]
        if g_val > peak_grid_kwh:
            peak_grid_kwh = g_val
            
    return hourly_plans, round(total_grid_kwh, 4), round(total_cost_bdt, 4), round(peak_grid_kwh, 4)
