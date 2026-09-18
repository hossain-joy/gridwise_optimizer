import re
import json

def parse_hour(h_str, default_meridiem=None):
    h_str = h_str.strip().lower()
    if h_str in ["noon", "midday"]:
        return 12
    if h_str == "midnight":
        return 0
    m = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$", h_str)
    if not m:
        return None
    hr = int(m.group(1))
    mer = m.group(3) or default_meridiem
    if mer == "pm" and hr != 12:
        hr += 12
    elif mer == "am" and hr == 12:
        hr = 0
    return hr

def extract_time_window(text):
    text_clean = text.lower()
    # Support military time e.g. 13:00 to 15:00 or 13:00-15:00
    m_mil = re.search(r"\b(\d{1,2}):00\s*(?:to|-|until|and)\s*(\d{1,2}):00\b", text_clean)
    if m_mil:
        s_hr, e_hr = int(m_mil.group(1)), int(m_mil.group(2))
        if 0 <= s_hr < e_hr <= 24:
            return list(range(s_hr, min(e_hr, 24)))

    pattern = r"(?:from|between|during)?\s*(\b\d{1,2}(?::\d{2})?\s*(?:am|pm)?|\bnoon|\bmidnight)\s*(?:until|to|and|-)\s*(\b\d{1,2}(?::\d{2})?\s*(?:am|pm)?|\bnoon|\bmidnight)"
    m = re.search(pattern, text_clean)
    if not m:
        return []
    s_str, e_str = m.group(1), m.group(2)
    end_mer = "pm" if "pm" in e_str else ("am" if "am" in e_str else None)
    start_mer = "pm" if "pm" in s_str else ("am" if "am" in s_str else None)
    
    e_hr = parse_hour(e_str)
    if e_str == "midnight":
        e_hr = 24
    
    if not start_mer:
        if s_str in ["noon", "midday"]:
            s_hr = 12
        elif s_str == "midnight":
            s_hr = 0
        else:
            raw_s = int(re.match(r"\d+", s_str).group(0))
            if end_mer == "pm":
                if raw_s >= 8 and raw_s <= 11:
                    s_hr = raw_s
                elif raw_s < 12 and (raw_s + 12) < e_hr:
                    s_hr = raw_s + 12
                elif raw_s < 12 and e_hr <= 12:
                    s_hr = raw_s
                else:
                    s_hr = raw_s
            elif end_mer == "am":
                s_hr = raw_s if raw_s != 12 else 0
            else:
                s_hr = raw_s
    else:
        s_hr = parse_hour(s_str)
        
    if s_hr is not None and e_hr is not None and 0 <= s_hr < e_hr <= 24:
        return list(range(s_hr, min(e_hr, 24)))
    return []

def extract_rule_directive(note: str, note_idx: int, capacity_kwh: float = 500.0) -> dict:
    text = note.strip()
    low = text.lower()
    
    # Check for distractors / non-operational notes
    distractor_keywords = [
        "sports office", "registration deadline", "library", "book-return",
        "student affairs", "club notices", "seminar room", "cafeteria", "town hall",
        "coffee provided", "next week", "next month"
    ]
    if any(k in low for k in distractor_keywords) and not any(k in low for k in ["battery", "solar", "grid", "feeder", "transformer", "substation"]):
        return {
            "note_index": note_idx,
            "applies": False,
            "directive_type": "no_op",
            "structured_adjustment": None,
            "explanation": "This note does not affect today's 24-hour energy schedule."
        }
        
    hours = extract_time_window(text)
    if not hours:
        return {
            "note_index": note_idx,
            "applies": False,
            "directive_type": "no_op",
            "structured_adjustment": None,
            "explanation": "No applicable time window found or unrelated note."
        }
        
    # 1. Solar reduction
    if any(w in low for w in ["solar", "pv", "panel", "photovoltaic", "rooftop"]) and any(w in low for w in ["wash", "cleaning", "clean", "cloud", "reduction", "reduce", "drop", "fall", "inverter", "leave about"]):
        factor = None
        m_remain = re.search(r"(?:treated as|drops to|leave|at|remain(?:ing)?|about)\s*(?:roughly|~)?\s*(\d+(?:\.\d+)?)\s*%", low)
        if m_remain:
            factor = round(float(m_remain.group(1)) / 100.0, 4)
        elif "half" in low:
            factor = 0.5
        else:
            m_red = re.search(r"(\d+(?:\.\d+)?)\s*%\s*(?:reduction|fall|drop)", low) or re.search(r"(?:fall|drop|reduce)\s*by\s*(\d+(?:\.\d+)?)\s*%", low)
            if m_red:
                red_pct = float(m_red.group(1))
                factor = round((100.0 - red_pct) / 100.0, 4)
                
        if factor is not None:
            return {
                "note_index": note_idx,
                "applies": True,
                "directive_type": "solar_reduction",
                "structured_adjustment": {"hours": hours, "factor": factor},
                "explanation": f"Solar availability reduced to factor {factor} during specified window."
            }

    # 2. No charge window
    if any(w in low for w in ["charge", "charger", "charging"]) and not any(w in low for w in ["discharge", "discharging"]) and any(w in low for w in ["isolated", "unavailable", "disabled", "offline", "do not charge", "cannot charge", "maintenance", "outage"]):
        return {
            "note_index": note_idx,
            "applies": True,
            "directive_type": "no_charge_window",
            "structured_adjustment": {"hours": hours},
            "explanation": "Battery charging is disabled during the specified maintenance window."
        }

    # 3. No discharge window
    if any(w in low for w in ["discharge", "discharging"]) and any(w in low for w in ["not discharge", "must not discharge", "offline", "disabled", "unavailable", "do not discharge", "testing", "protection"]):
        return {
            "note_index": note_idx,
            "applies": True,
            "directive_type": "no_discharge_window",
            "structured_adjustment": {"hours": hours},
            "explanation": "Battery discharging is disabled during the specified window."
        }

    # 4. Minimum battery reserve
    if any(w in low for w in ["battery", "stored in the battery", "remain in the battery", "reserve", "hold at least", "keep at least", "requires at least", "data center"]):
        m_pct = re.search(r"(\d+(?:\.\d+)?)\s*%\s*(?:of\s*(?:the\s*)?(?:battery\s*)?capacity)?", low)
        if m_pct and "capacity" in low:
            pct = float(m_pct.group(1))
            min_kwh = round((pct / 100.0) * capacity_kwh, 2)
            return {
                "note_index": note_idx,
                "applies": True,
                "directive_type": "minimum_battery_reserve",
                "structured_adjustment": {"hours": hours, "minimum_energy_kwh": min_kwh},
                "explanation": f"Battery reserve maintained at {min_kwh} kWh ({pct}% of capacity)."
            }
        m_kwh = re.search(r"(\d+(?:\.\d+)?)\s*kwh", low)
        if m_kwh:
            min_kwh = float(m_kwh.group(1))
            return {
                "note_index": note_idx,
                "applies": True,
                "directive_type": "minimum_battery_reserve",
                "structured_adjustment": {"hours": hours, "minimum_energy_kwh": min_kwh},
                "explanation": f"Battery reserve maintained at {min_kwh} kWh."
            }

    # 5. Max grid window
    if any(w in low for w in ["grid", "feeder", "transformer", "substation", "import", "intake"]):
        m_kwh = re.search(r"(\d+(?:\.\d+)?)\s*kwh", low)
        if m_kwh:
            max_kwh = float(m_kwh.group(1))
            return {
                "note_index": note_idx,
                "applies": True,
                "directive_type": "max_grid_window",
                "structured_adjustment": {"hours": hours, "max_grid_kwh": max_kwh},
                "explanation": f"Grid import capped at {max_kwh} kWh."
            }

    return {
        "note_index": note_idx,
        "applies": False,
        "directive_type": "no_op",
        "structured_adjustment": None,
        "explanation": "Unrelated note or no applicable directive."
    }

def test_all():
    with open("tests/sample_cases.json") as f:
        cases = json.load(f)["cases"]

    all_matched = True
    for case in cases:
        cid = case["id"]
        cap = case["input"]["battery"]["capacity_kwh"]
        exp_directives = case["expected_output"]["directive_interpretation"]
        for idx, note in enumerate(case["input"]["operator_notes"]):
            extracted = extract_rule_directive(note, idx, cap)
            exp = exp_directives[idx]
            
            matches = (
                extracted["directive_type"] == exp["directive_type"] and
                extracted["applies"] == exp["applies"] and
                extracted["structured_adjustment"] == exp["structured_adjustment"]
            )
            if not matches:
                all_matched = False
                print(f"MISMATCH in {cid} Note {idx}:")
                print(f"  Note: {note}")
                print(f"  Extracted: {extracted}")
                print(f"  Expected: {exp}")
            else:
                print(f"{cid} Note {idx}: MATCH ({extracted['directive_type']})")

    print("\nALL DIRECTIVES MATCHED EXACTLY:", all_matched)
    assert all_matched

if __name__ == "__main__":
    test_all()
