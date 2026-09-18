from app.guardrail import validate_directive
from app.models import DirectiveInterpretation

def test_guardrail_valid_solar_reduction():
    raw = {
        "note_index": 0,
        "applies": True,
        "directive_type": "solar_reduction",
        "structured_adjustment": {
            "hours": [13, 14],
            "factor": 0.2
        },
        "explanation": "Valid test"
    }
    res = validate_directive(raw, note_count=1, capacity_kwh=500.0, scenario_id="test")
    assert res.directive_type == "solar_reduction"
    assert res.applies is True

def test_guardrail_extra_keys_downgrade():
    raw = {
        "note_index": 0,
        "applies": True,
        "directive_type": "solar_reduction",
        "structured_adjustment": {
            "hours": [13, 14],
            "factor": 0.2,
            "extra_key": "bad"
        },
        "explanation": "Extra key should trigger downgrade"
    }
    res = validate_directive(raw, note_count=1, capacity_kwh=500.0, scenario_id="test")
    assert res.directive_type == "no_op"
    assert res.applies is False

def test_guardrail_invalid_factor():
    raw = {
        "note_index": 0,
        "applies": True,
        "directive_type": "solar_reduction",
        "structured_adjustment": {
            "hours": [13, 14],
            "factor": 1.5
        },
        "explanation": "Factor > 1 should downgrade"
    }
    res = validate_directive(raw, note_count=1, capacity_kwh=500.0, scenario_id="test")
    assert res.directive_type == "no_op"

def test_guardrail_no_op_valid():
    raw = {
        "note_index": 0,
        "applies": False,
        "directive_type": "no_op",
        "structured_adjustment": None,
        "explanation": "No operation valid"
    }
    res = validate_directive(raw, note_count=1, capacity_kwh=500.0, scenario_id="test")
    assert res.directive_type == "no_op"
    
def test_guardrail_no_op_invalid_applies():
    raw = {
        "note_index": 0,
        "applies": True,
        "directive_type": "no_op",
        "structured_adjustment": None,
        "explanation": "applies should be false"
    }
    res = validate_directive(raw, note_count=1, capacity_kwh=500.0, scenario_id="test")
    assert res.directive_type == "no_op"
    assert res.applies is False

def test_guardrail_capacity_bound():
    raw = {
        "note_index": 0,
        "applies": True,
        "directive_type": "minimum_battery_reserve",
        "structured_adjustment": {
            "hours": [1],
            "minimum_energy_kwh": 600.0
        },
        "explanation": "Exceeds capacity"
    }
    res = validate_directive(raw, note_count=1, capacity_kwh=500.0, scenario_id="test")
    assert res.directive_type == "no_op"
