import json
import pulp
from app.models import OptimizeRequest, DirectiveInterpretation
from app.guardrail import apply_directives, validate_directive
from app.optimizer import run_optimizer
from app.replay import validate_replay

def create_base_hours():
    demands = [80, 75, 70, 70, 75, 85, 100, 120, 140, 155, 165, 175, 180, 175, 165, 160, 170, 185, 205, 215, 205, 175, 135, 100]
    solars =  [ 0,  0,  0,  0,  0,  0,   5,  15,  45,  85, 125, 160, 180, 170, 135,  85,  40,  10,   0,   0,   0,   0,   0,   0]
    tariffs = [ 6,  6,  5,  5,  5,  6,   8,  10,  12,  14,  15,  16,  16,  15,  14,  14,  18,  22,  28,  31,  27,  19,  11,   7]
    return [{"hour": h, "demand_kwh": demands[h], "solar_kwh": solars[h], "tariff_bdt_per_kwh": tariffs[h]} for h in range(24)]

def solve_case(case_id, label, notes, battery, exp_dirs):
    hours = create_base_hours()
    req_dict = {
        "scenario_id": case_id,
        "operator_notes": notes,
        "hours": hours,
        "battery": battery
    }
    req = OptimizeRequest(**req_dict)
    
    # Compute ground truth optimal solution
    directives = [validate_directive(d, len(notes), battery["capacity_kwh"], case_id) for d in exp_dirs]
    demand, solar, tariff, active_min_reserve, active_max_grid, can_charge, can_discharge = apply_directives(req, directives)
    
    hourly_plans, total_grid, total_cost, peak_grid = run_optimizer(
        demand, solar, tariff, battery,
        active_min_reserve, active_max_grid, can_charge, can_discharge
    )
    
    # Verify replay
    validate_replay(
        hourly_plans, demand, solar, tariff, battery,
        active_min_reserve, active_max_grid, can_charge, can_discharge
    )
    
    plans_json = [p.model_dump() for p in hourly_plans]
    
    return {
        "id": case_id,
        "label": label,
        "input": req_dict,
        "expected_output": {
            "scenario_id": case_id,
            "directive_interpretation": exp_dirs,
            "hourly_plan": plans_json,
            "total_grid_kwh": total_grid,
            "total_cost_bdt": total_cost,
            "peak_grid_kwh": peak_grid,
            "plan_summary": f"Optimal schedule computed for {label}."
        }
    }

def generate_all_20():
    bat_std = {"capacity_kwh": 240.0, "initial_energy_kwh": 120.0, "minimum_energy_kwh": 40.0, "max_charge_kwh_per_hour": 60.0, "max_discharge_kwh_per_hour": 60.0}
    bat_large = {"capacity_kwh": 300.0, "initial_energy_kwh": 150.0, "minimum_energy_kwh": 50.0, "max_charge_kwh_per_hour": 75.0, "max_discharge_kwh_per_hour": 75.0}
    bat_compact = {"capacity_kwh": 200.0, "initial_energy_kwh": 100.0, "minimum_energy_kwh": 30.0, "max_charge_kwh_per_hour": 50.0, "max_discharge_kwh_per_hour": 50.0}
    
    cases = []
    
    # 11: Complex Solar Reduction
    cases.append(solve_case(
        "SYNTH-11", "Overcast afternoon solar drop",
        ["Rooftop PV output will drop by 75% between 1 PM and 4 PM due to heavy overcast."],
        bat_std,
        [{"note_index": 0, "applies": True, "directive_type": "solar_reduction", "structured_adjustment": {"hours": [13, 14, 15], "factor": 0.25}, "explanation": "75% drop leaves 25% usable solar factor."}]
    ))

    # 12: Night-time No-Discharge
    cases.append(solve_case(
        "SYNTH-12", "Night relay upgrade no-discharge",
        ["Battery discharging is disabled from 8 PM until 11 PM during system relay upgrades."],
        bat_std,
        [{"note_index": 0, "applies": True, "directive_type": "no_discharge_window", "structured_adjustment": {"hours": [20, 21, 22]}, "explanation": "Discharge disabled during upgrade."}]
    ))

    # 13: Morning Charger Outage + Distractor
    cases.append(solve_case(
        "SYNTH-13", "Morning charger maintenance + distractor",
        [
            "The charging unit is unavailable between 6 AM and 9 AM for electrical inspection.",
            "The annual campus debate competition will start next Monday."
        ],
        bat_std,
        [
            {"note_index": 0, "applies": True, "directive_type": "no_charge_window", "structured_adjustment": {"hours": [6, 7, 8]}, "explanation": "Charger unavailable in morning window."},
            {"note_index": 1, "applies": False, "directive_type": "no_op", "structured_adjustment": None, "explanation": "Debate announcement does not affect energy schedule."}
        ]
    ))

    # 14: Emergency Reserve as Percentage (40% of 300 = 120 kWh)
    cases.append(solve_case(
        "SYNTH-14", "Evening critical lab reserve percentage",
        ["Hold at least 40% of the battery capacity in the battery from 5 PM to 9 PM for critical lab experiments."],
        bat_large,
        [{"note_index": 0, "applies": True, "directive_type": "minimum_battery_reserve", "structured_adjustment": {"hours": [17, 18, 19, 20], "minimum_energy_kwh": 120.0}, "explanation": "40% of 300 kWh capacity equals 120 kWh."}]
    ))

    # 15: Substation Feeder Grid Cap
    cases.append(solve_case(
        "SYNTH-15", "Substation feeder constraint",
        ["From 6 PM until 10 PM, campus grid import must not exceed 165 kWh in any hour due to feeder maintenance."],
        bat_std,
        [{"note_index": 0, "applies": True, "directive_type": "max_grid_window", "structured_adjustment": {"hours": [18, 19, 20, 21], "max_grid_kwh": 165.0}, "explanation": "Grid import capped at 165 kWh."}]
    ))

    # 16: Two Hard Directives + Distractor
    cases.append(solve_case(
        "SYNTH-16", "Solar cleaning + charging outage + distractor",
        [
            "Solar panels will be washed between 11 AM and 1 PM; expect only 30% of standard output.",
            "Do not charge the battery between 2 PM and 4 PM while the circuit is tested.",
            "Faculty club meeting scheduled for 3 PM in building B."
        ],
        bat_std,
        [
            {"note_index": 0, "applies": True, "directive_type": "solar_reduction", "structured_adjustment": {"hours": [11, 12], "factor": 0.3}, "explanation": "Solar reduced to factor 0.3 during washing."},
            {"note_index": 1, "applies": True, "directive_type": "no_charge_window", "structured_adjustment": {"hours": [14, 15]}, "explanation": "Charging blocked 14:00-16:00."},
            {"note_index": 2, "applies": False, "directive_type": "no_op", "structured_adjustment": None, "explanation": "Club meeting is a distractor."}
        ]
    ))

    # 17: Extreme Solar Drop (20% remaining)
    cases.append(solve_case(
        "SYNTH-17", "Dust storm severe solar drop",
        ["Dust storm from noon until 3 PM will leave roughly 20% of normal solar output."],
        bat_std,
        [{"note_index": 0, "applies": True, "directive_type": "solar_reduction", "structured_adjustment": {"hours": [12, 13, 14], "factor": 0.2}, "explanation": "Solar drops to 0.2 factor."}]
    ))

    # 18: Early Morning No-Charge + Evening Grid Cap
    cases.append(solve_case(
        "SYNTH-18", "Morning charger isolation + evening grid limit",
        [
            "The battery charger will be isolated from 1 AM until 4 AM for maintenance.",
            "The transformer limit is 170 kWh of grid import from 7 PM until 9 PM."
        ],
        bat_std,
        [
            {"note_index": 0, "applies": True, "directive_type": "no_charge_window", "structured_adjustment": {"hours": [1, 2, 3]}, "explanation": "Charging isolated 01:00-04:00."},
            {"note_index": 1, "applies": True, "directive_type": "max_grid_window", "structured_adjustment": {"hours": [19, 20], "max_grid_kwh": 170.0}, "explanation": "Grid capped at 170 kWh."}
        ]
    ))

    # 19: High Reserve Requirement (Absolute kWh) + Distractor
    cases.append(solve_case(
        "SYNTH-19", "High emergency reserve + library distractor",
        [
            "Keep at least 180 kWh stored in the battery from 6 PM until 10 PM for emergency services.",
            "The library is extending book-return hours next week."
        ],
        bat_large,
        [
            {"note_index": 0, "applies": True, "directive_type": "minimum_battery_reserve", "structured_adjustment": {"hours": [18, 19, 20, 21], "minimum_energy_kwh": 180.0}, "explanation": "180 kWh reserve required."},
            {"note_index": 1, "applies": False, "directive_type": "no_op", "structured_adjustment": None, "explanation": "Library notice is distractor."}
        ]
    ))

    # 20: Full Afternoon No-Discharge
    cases.append(solve_case(
        "SYNTH-20", "Afternoon protection test no-discharge",
        ["For protection testing, the battery must not discharge from 1 PM until 5 PM."],
        bat_std,
        [{"note_index": 0, "applies": True, "directive_type": "no_discharge_window", "structured_adjustment": {"hours": [13, 14, 15, 16]}, "explanation": "Discharge forbidden 13:00-17:00."}]
    ))

    # 21: Solar decrease by 60% (factor 0.4)
    cases.append(solve_case(
        "SYNTH-21", "Midday cloud cover reduction",
        [
            "Cloud cover causes rooftop PV to fall by 60% from 10 AM until 1 PM.",
            "The student affairs office will publish club notices tomorrow."
        ],
        bat_std,
        [
            {"note_index": 0, "applies": True, "directive_type": "solar_reduction", "structured_adjustment": {"hours": [10, 11, 12], "factor": 0.4}, "explanation": "60% fall leaves factor 0.4."},
            {"note_index": 1, "applies": False, "directive_type": "no_op", "structured_adjustment": None, "explanation": "Club notice is distractor."}
        ]
    ))

    # 22: Three Active Directives
    cases.append(solve_case(
        "SYNTH-22", "Triple active constraints scenario",
        [
            "Solar production drops to ~40% of normal from 11 AM to 2 PM.",
            "Battery charging is disabled from 1 PM until 3 PM while technicians inspect the charger.",
            "Grid intake must stay at or below 170 kWh from 6 PM until 9 PM."
        ],
        bat_std,
        [
            {"note_index": 0, "applies": True, "directive_type": "solar_reduction", "structured_adjustment": {"hours": [11, 12, 13], "factor": 0.4}, "explanation": "Solar at 40% factor."},
            {"note_index": 1, "applies": True, "directive_type": "no_charge_window", "structured_adjustment": {"hours": [13, 14]}, "explanation": "Charger disabled 13:00-15:00."},
            {"note_index": 2, "applies": True, "directive_type": "max_grid_window", "structured_adjustment": {"hours": [18, 19, 20], "max_grid_kwh": 170.0}, "explanation": "Grid capped at 170 kWh."}
        ]
    ))

    # 23: Complete Solar Replacement Outage
    cases.append(solve_case(
        "SYNTH-23", "Midday inverter replacement complete outage",
        ["Solar panels offline from noon until 2 PM for inverter replacement, usable solar drops to 0%."],
        bat_std,
        [{"note_index": 0, "applies": True, "directive_type": "solar_reduction", "structured_adjustment": {"hours": [12, 13], "factor": 0.0}, "explanation": "Zero solar during replacement."}]
    ))

    # 24: Midnight to Morning Window
    cases.append(solve_case(
        "SYNTH-24", "Midnight charger isolation",
        [
            "Do not charge the battery from midnight until 3 AM during grid synchronization.",
            "The sports office moved next month's registration deadline."
        ],
        bat_std,
        [
            {"note_index": 0, "applies": True, "directive_type": "no_charge_window", "structured_adjustment": {"hours": [0, 1, 2]}, "explanation": "Charging disabled midnight to 3 AM."},
            {"note_index": 1, "applies": False, "directive_type": "no_op", "structured_adjustment": None, "explanation": "Sports deadline is distractor."}
        ]
    ))

    # 25: Double Distractors + 1 Active Reserve
    cases.append(solve_case(
        "SYNTH-25", "Critical server reserve with dual distractors",
        [
            "Reminder: Town hall meeting in the cafeteria at 2 PM, coffee provided.",
            "The data center requires at least 150 kWh to remain in the battery from 7 PM until 10 PM.",
            "A seminar room booking was moved to next week."
        ],
        bat_large,
        [
            {"note_index": 0, "applies": False, "directive_type": "no_op", "structured_adjustment": None, "explanation": "Town hall is distractor."},
            {"note_index": 1, "applies": True, "directive_type": "minimum_battery_reserve", "structured_adjustment": {"hours": [19, 20, 21], "minimum_energy_kwh": 150.0}, "explanation": "150 kWh server reserve required."},
            {"note_index": 2, "applies": False, "directive_type": "no_op", "structured_adjustment": None, "explanation": "Seminar booking is distractor."}
        ]
    ))

    # 26: 24h Military Format (18:00 to 21:00)
    cases.append(solve_case(
        "SYNTH-26", "Military time evening transformer limit",
        ["Transformer limit is 170 kWh of grid import between 18:00 and 21:00."],
        bat_std,
        [{"note_index": 0, "applies": True, "directive_type": "max_grid_window", "structured_adjustment": {"hours": [18, 19, 20], "max_grid_kwh": 170.0}, "explanation": "Grid capped at 170 kWh."}]
    ))

    # 27: Charger & Discharge at different hours
    cases.append(solve_case(
        "SYNTH-27", "Separate morning charge and evening discharge restrictions",
        [
            "Battery charging is disabled from 9 AM until 11 AM.",
            "Do not discharge the battery from 4 PM until 6 PM during relay testing."
        ],
        bat_std,
        [
            {"note_index": 0, "applies": True, "directive_type": "no_charge_window", "structured_adjustment": {"hours": [9, 10]}, "explanation": "No charge 09:00-11:00."},
            {"note_index": 1, "applies": True, "directive_type": "no_discharge_window", "structured_adjustment": {"hours": [16, 17]}, "explanation": "No discharge 16:00-18:00."}
        ]
    ))

    # 28: Percentage Reserve (70% of 200 = 140 kWh)
    cases.append(solve_case(
        "SYNTH-28", "High storm reserve percentage",
        ["Keep at least 70% of the battery capacity stored in the battery from 6 PM until 9 PM for emergency operations."],
        bat_compact,
        [{"note_index": 0, "applies": True, "directive_type": "minimum_battery_reserve", "structured_adjustment": {"hours": [18, 19, 20], "minimum_energy_kwh": 140.0}, "explanation": "70% of 200 kWh capacity equals 140 kWh."}]
    ))

    # 29: Tight Feeder Cap + Career Distractor
    cases.append(solve_case(
        "SYNTH-29", "Tight feeder limit + career distractor",
        [
            "Campus grid import must not exceed 165 kWh from 5 PM until 8 PM because the feeder is operating under a temporary limit.",
            "The career fair registration opens next Friday."
        ],
        bat_std,
        [
            {"note_index": 0, "applies": True, "directive_type": "max_grid_window", "structured_adjustment": {"hours": [17, 18, 19], "max_grid_kwh": 165.0}, "explanation": "Feeder capped at 165 kWh."},
            {"note_index": 1, "applies": False, "directive_type": "no_op", "structured_adjustment": None, "explanation": "Career fair is distractor."}
        ]
    ))

    # 30: All Distractors (All No-Ops)
    cases.append(solve_case(
        "SYNTH-30", "All distractor notes scenario",
        [
            "The campus bookstore offers discounts this weekend.",
            "Parking lot B will be closed for repaving tomorrow.",
            "Guest lecture on AI scheduled at 3 PM in the auditorium."
        ],
        bat_std,
        [
            {"note_index": 0, "applies": False, "directive_type": "no_op", "structured_adjustment": None, "explanation": "Bookstore notice is distractor."},
            {"note_index": 1, "applies": False, "directive_type": "no_op", "structured_adjustment": None, "explanation": "Parking notice is distractor."},
            {"note_index": 2, "applies": False, "directive_type": "no_op", "structured_adjustment": None, "explanation": "Lecture notice is distractor."}
        ]
    ))

    with open("tests/extended_cases.json", "w") as f:
        json.dump({"cases": cases}, f, indent=2)
    print(f"Successfully generated {len(cases)} extended test cases in tests/extended_cases.json")

if __name__ == "__main__":
    generate_all_20()
