from typing import List, Tuple
from .models import HourlyPlan

def validate_replay(
    plan: List[HourlyPlan],
    demand: List[float],
    effective_solar: List[float],
    tariff: List[float],
    battery: dict,
    active_min_reserve: List[float],
    active_max_grid: List[float],
    can_charge: List[bool],
    can_discharge: List[bool]
) -> Tuple[float, float, float]:
    """
    Independently replay the schedule and assert constraints.
    Returns computed (total_grid_kwh, total_cost_bdt, peak_grid_kwh)
    """
    if len(plan) != 24:
        raise ValueError("Plan must have exactly 24 hours")
        
    hours = [h.hour for h in plan]
    if hours != list(range(24)):
        raise ValueError("Plan hours must be exactly 0 to 23 in order")
        
    total_grid = 0.0
    total_cost = 0.0
    peak_grid = 0.0
    
    TOL = 0.01
    
    for h in range(24):
        p = plan[h]
        
        # 1. Energy balance
        discharge = p.battery_kwh if p.battery_action == "discharge" else 0.0
        charge = p.battery_kwh if p.battery_action == "charge" else 0.0
        
        supply = p.grid_kwh + p.solar_used_kwh + discharge
        req = demand[h] + charge
        
        if abs(supply - req) > TOL:
            raise ValueError(f"Energy balance failed at hour {h}: supply={supply} vs demand+charge={req}")
            
        # 2. Solar usage <= effective solar
        if p.solar_used_kwh > effective_solar[h] + TOL:
            raise ValueError(f"Used more solar than available at hour {h}")
            
        # 3. Grid limits
        if p.grid_kwh > active_max_grid[h] + TOL:
            raise ValueError(f"Grid limit exceeded at hour {h}")
            
        # 4. Battery rate limits
        if charge > 0 and not can_charge[h]:
            raise ValueError(f"Charged during no_charge window at hour {h}")
        if discharge > 0 and not can_discharge[h]:
            raise ValueError(f"Discharged during no_discharge window at hour {h}")
        if charge > battery["max_charge_kwh_per_hour"] + TOL:
            raise ValueError(f"Exceeded max charge rate at hour {h}")
        if discharge > battery["max_discharge_kwh_per_hour"] + TOL:
            raise ValueError(f"Exceeded max discharge rate at hour {h}")
            
        # 5. Battery state
        prev_energy = plan[h-1].battery_energy_after_kwh if h > 0 else battery["initial_energy_kwh"]
        expected_energy = prev_energy + charge - discharge
        if abs(p.battery_energy_after_kwh - expected_energy) > TOL:
            raise ValueError(f"Battery state transition failed at hour {h}: expected {expected_energy}, got {p.battery_energy_after_kwh}")
            
        # 6. Battery bounds
        if p.battery_energy_after_kwh < active_min_reserve[h] - TOL:
            raise ValueError(f"Battery fell below min reserve at hour {h}: {p.battery_energy_after_kwh} < {active_min_reserve[h]}")
        if p.battery_energy_after_kwh > battery["capacity_kwh"] + TOL:
            raise ValueError(f"Battery exceeded capacity at hour {h}")
            
        total_grid += p.grid_kwh
        total_cost += p.grid_kwh * tariff[h]
        if p.grid_kwh > peak_grid:
            peak_grid = p.grid_kwh
            
    # Terminal constraint
    if abs(plan[-1].battery_energy_after_kwh - battery["initial_energy_kwh"]) > TOL:
        raise ValueError("Did not return to initial energy at end of day")
        
    return total_grid, total_cost, peak_grid
