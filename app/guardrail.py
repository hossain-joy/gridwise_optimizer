import logging
from typing import List, Dict, Any, Optional
from pydantic import ValidationError
from .models import OptimizeRequest, DirectiveInterpretation, StructuredAdjustment

logger = logging.getLogger(__name__)

def _is_strictly_equal_keys(actual: dict, expected_keys: set) -> bool:
    return set(actual.keys()) == expected_keys

def validate_directive(raw: dict, note_count: int, capacity_kwh: float, scenario_id: str) -> DirectiveInterpretation:
    """
    Validates a raw dictionary from the LLM and forces it to a Safe DirectiveInterpretation.
    Downgrades to no_op if any strict constraints are violated.
    """
    def _fallback(reason: str) -> DirectiveInterpretation:
        idx = raw.get("note_index", 0)
        if not isinstance(idx, int) or idx < 0 or idx >= note_count:
            idx = 0  # Ultimate fallback
        logger.warning(f"Guardrail downgrade for note_index={idx} in scenario={scenario_id}: {reason}")
        return DirectiveInterpretation(
            note_index=idx,
            applies=False,
            directive_type="no_op",
            structured_adjustment=None,
            explanation=raw.get("explanation", "Fallback to no_op due to validation failure")
        )

    try:
        # 1. Pydantic initial parse to check types and boundaries
        parsed = DirectiveInterpretation(**raw)
    except Exception as e:
        return _fallback(f"Pydantic validation failed: {str(e)}")

    # 2. Check note_index bounds (Pydantic only checked 0..2, need 0..note_count-1)
    if parsed.note_index >= note_count:
        return _fallback(f"note_index {parsed.note_index} out of bounds for note_count {note_count}")

    # 3. Applies semantics and exact shape checking
    adj = raw.get("structured_adjustment")
    dtype = parsed.directive_type

    if dtype == "no_op":
        if parsed.applies is not False:
            return _fallback("no_op must have applies=False")
        if adj is not None:
            return _fallback("no_op must have structured_adjustment=null")
        return parsed

    if not parsed.applies:
        return _fallback(f"{dtype} must have applies=True")

    if adj is None or not isinstance(adj, dict):
        return _fallback(f"{dtype} requires a structured_adjustment dictionary")

    # 4. Hours validation
    hours = adj.get("hours")
    if not isinstance(hours, list) or len(hours) == 0:
        return _fallback("non-no_op directives must have a non-empty list of hours")
    
    # Check if hours are unique, ints, 0-23, and ascending
    if not all(isinstance(h, int) for h in hours):
        return _fallback("hours must be integers")
    if any(h < 0 or h > 23 for h in hours):
        return _fallback("hours must be between 0 and 23")
    if hours != sorted(list(set(hours))):
        return _fallback("hours must be unique and in ascending order")

    # 5. Exact shape checking for specific directive types
    if dtype == "solar_reduction":
        if not _is_strictly_equal_keys(adj, {"hours", "factor"}):
            return _fallback("solar_reduction structured_adjustment must have exactly 'hours' and 'factor'")
        factor = adj.get("factor")
        if not isinstance(factor, (int, float)) or factor < 0 or factor > 1:
            return _fallback("factor must be between 0.0 and 1.0")

    elif dtype == "minimum_battery_reserve":
        if not _is_strictly_equal_keys(adj, {"hours", "minimum_energy_kwh"}):
            return _fallback("minimum_battery_reserve structured_adjustment must have exactly 'hours' and 'minimum_energy_kwh'")
        min_kwh = adj.get("minimum_energy_kwh")
        if not isinstance(min_kwh, (int, float)) or min_kwh < 0 or min_kwh > capacity_kwh:
            return _fallback(f"minimum_energy_kwh must be between 0 and capacity_kwh ({capacity_kwh})")

    elif dtype in ["no_charge_window", "no_discharge_window"]:
        if not _is_strictly_equal_keys(adj, {"hours"}):
            return _fallback(f"{dtype} structured_adjustment must have exactly 'hours'")

    elif dtype == "max_grid_window":
        if not _is_strictly_equal_keys(adj, {"hours", "max_grid_kwh"}):
            return _fallback("max_grid_window structured_adjustment must have exactly 'hours' and 'max_grid_kwh'")
        max_grid = adj.get("max_grid_kwh")
        if not isinstance(max_grid, (int, float)) or max_grid < 0:
            return _fallback("max_grid_kwh must be >= 0")

    return parsed

def apply_directives(
    request: OptimizeRequest,
    directives: List[DirectiveInterpretation]
) -> tuple[List[float], List[float], List[float], List[float], List[bool], List[bool]]:
    """
    Parses request and valid directives to generate lists for the optimizer.
    Returns: (demand, solar, tariff, active_min_reserve, active_max_grid, can_charge, can_discharge)
    """
    hours = sorted(request.hours, key=lambda h: h.hour)
    
    demand = [h.demand_kwh for h in hours]
    solar = [h.solar_kwh for h in hours]
    tariff = [h.tariff_bdt_per_kwh for h in hours]
    
    active_min_reserve = [request.battery.minimum_energy_kwh] * 24
    active_max_grid = [float('inf')] * 24
    can_charge = [True] * 24
    can_discharge = [True] * 24
    
    for directive in directives:
        if not directive.applies or directive.directive_type == "no_op":
            continue
            
        adj = directive.structured_adjustment
        if not adj:
            continue
            
        hours = adj.get("hours") if isinstance(adj, dict) else getattr(adj, "hours", None)
        if not hours:
            continue
            
        for h in hours:
            if h < 0 or h > 23:
                continue
                
            if directive.directive_type == "solar_reduction":
                factor = adj.get("factor") if isinstance(adj, dict) else getattr(adj, "factor", None)
                if factor is not None:
                    solar[h] *= factor
            elif directive.directive_type == "minimum_battery_reserve":
                min_kwh = adj.get("minimum_energy_kwh") if isinstance(adj, dict) else getattr(adj, "minimum_energy_kwh", None)
                if min_kwh is not None:
                    active_min_reserve[h] = max(active_min_reserve[h], min_kwh)
            elif directive.directive_type == "no_charge_window":
                can_charge[h] = False
            elif directive.directive_type == "no_discharge_window":
                can_discharge[h] = False
            elif directive.directive_type == "max_grid_window":
                max_grid = adj.get("max_grid_kwh") if isinstance(adj, dict) else getattr(adj, "max_grid_kwh", None)
                if max_grid is not None:
                    if active_max_grid[h] == float('inf'):
                        active_max_grid[h] = max_grid
                    else:
                        active_max_grid[h] = min(active_max_grid[h], max_grid)
                        
    return demand, solar, tariff, active_min_reserve, active_max_grid, can_charge, can_discharge
