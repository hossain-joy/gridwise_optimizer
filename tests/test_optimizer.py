import pytest
from app.optimizer import run_optimizer

def test_optimizer_basic():
    demand = [100.0] * 24
    solar = [0.0] * 24
    tariff = [10.0] * 24
    # Make night expensive
    for h in range(18, 22):
        tariff[h] = 20.0
        
    battery = {
        "capacity_kwh": 500.0,
        "initial_energy_kwh": 200.0,
        "minimum_energy_kwh": 50.0,
        "max_charge_kwh_per_hour": 100.0,
        "max_discharge_kwh_per_hour": 100.0
    }
    
    active_min_reserve = [50.0] * 24
    active_max_grid = [float('inf')] * 24
    can_charge = [True] * 24
    can_discharge = [True] * 24
    
    hourly_plans, total_grid, total_cost, peak_grid = run_optimizer(
        demand, solar, tariff, battery,
        active_min_reserve, active_max_grid, can_charge, can_discharge
    )
    
    assert len(hourly_plans) == 24
    
    # Check end of day neutrality
    assert abs(hourly_plans[-1].battery_energy_after_kwh - 200.0) < 0.001
    
    # Check demand + charge = grid + solar + discharge
    for h in range(24):
        plan = hourly_plans[h]
        discharge_kwh = plan.battery_kwh if plan.battery_action == 'discharge' else 0.0
        charge_kwh = plan.battery_kwh if plan.battery_action == 'charge' else 0.0
        
        balance_left = plan.grid_kwh + plan.solar_used_kwh + discharge_kwh
        balance_right = demand[h] + charge_kwh
        assert abs(balance_left - balance_right) < 0.001
