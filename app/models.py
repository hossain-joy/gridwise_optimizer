from pydantic import BaseModel, Field, model_validator, conlist, confloat
from typing import List, Optional, Literal, Dict, Any

class HourInput(BaseModel):
    hour: int = Field(..., ge=0, le=23)
    demand_kwh: float = Field(..., ge=0.0)
    solar_kwh: float = Field(..., ge=0.0)
    tariff_bdt_per_kwh: float = Field(..., ge=0.0)

class BatteryInput(BaseModel):
    capacity_kwh: float = Field(..., ge=0.0)
    initial_energy_kwh: float = Field(..., ge=0.0)
    minimum_energy_kwh: float = Field(..., ge=0.0)
    max_charge_kwh_per_hour: float = Field(..., ge=0.0)
    max_discharge_kwh_per_hour: float = Field(..., ge=0.0)

    @model_validator(mode="after")
    def check_min_capacity(self) -> "BatteryInput":
        if self.minimum_energy_kwh > self.capacity_kwh:
            raise ValueError("minimum_energy_kwh cannot exceed capacity_kwh")
        if self.initial_energy_kwh > self.capacity_kwh:
            raise ValueError("initial_energy_kwh cannot exceed capacity_kwh")
        if self.initial_energy_kwh < self.minimum_energy_kwh:
            raise ValueError("initial_energy_kwh cannot be less than minimum_energy_kwh")
        return self


class OptimizeRequest(BaseModel):
    scenario_id: str = Field(..., min_length=1)
    operator_notes: List[str] = Field(..., min_length=1, max_length=3)
    hours: List[HourInput] = Field(..., min_length=24, max_length=24)
    battery: BatteryInput

    @model_validator(mode="after")
    def check_hours_unique_and_complete(self) -> "OptimizeRequest":
        hour_indices = sorted([h.hour for h in self.hours])
        if hour_indices != list(range(24)):
            raise ValueError("hours array must contain exactly 24 unique entries for hours 0..23")
        
        # Ensure operator notes are not empty strings
        if any(not note.strip() for note in self.operator_notes):
            raise ValueError("operator_notes cannot contain empty strings")
            
        return self


class StructuredAdjustment(BaseModel):
    hours: Optional[List[int]] = None
    factor: Optional[float] = None
    minimum_energy_kwh: Optional[float] = None
    max_grid_kwh: Optional[float] = None

class DirectiveInterpretation(BaseModel):
    note_index: int = Field(..., ge=0, le=2)
    applies: bool
    directive_type: Literal[
        "solar_reduction", 
        "minimum_battery_reserve", 
        "no_charge_window", 
        "no_discharge_window", 
        "max_grid_window", 
        "no_op"
    ]
    structured_adjustment: Optional[Dict[str, Any]] = None
    explanation: str

class HourlyPlan(BaseModel):
    hour: int = Field(..., ge=0, le=23)
    grid_kwh: float = Field(..., ge=0.0)
    solar_used_kwh: float = Field(..., ge=0.0)
    battery_action: Literal["idle", "charge", "discharge"]
    battery_kwh: float = Field(..., ge=0.0)
    battery_energy_after_kwh: float = Field(..., ge=0.0)

class OptimizeResponse(BaseModel):
    scenario_id: str
    directive_interpretation: List[DirectiveInterpretation]
    hourly_plan: List[HourlyPlan]
    total_grid_kwh: float
    total_cost_bdt: float
    peak_grid_kwh: float
    plan_summary: str
