import os
import json
import re
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

load_dotenv()
logger = logging.getLogger(__name__)

# Cache dictionary: normalized_text -> dict (raw JSON response for that note)
_NOTE_CACHE: Dict[str, dict] = {}

def normalize_text(text: str) -> str:
    # Lowercase, strip whitespace and punctuation variance
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    return ' '.join(text.split())

def parse_hour(h_str: str, default_meridiem: Optional[str] = None) -> Optional[int]:
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

def extract_time_window(text: str) -> List[int]:
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
    """Deterministic NLP/regex fallback extractor for operator notes."""
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
    if (any(w in low for w in ["solar", "pv", "panel", "photovoltaic", "rooftop", "generation", "array"]) and
        any(w in low for w in ["wash", "washing", "cleaned", "cleaning", "clean", "cloud", "dust", "storm", "soot", "haze", "reduction", "reduce", "drop", "fall", "inverter", "leave", "only", "degraded", "curtail", "maintenance"])):
        factor = None
        m_remain = (
            re.search(r"(?:treated as|drops to|drop to|fall to|leave|leaves|at|remain(?:ing)?|about|only|roughly|expect only)\s*(?:roughly|about|~)?\s*(\d+(?:\.\d+)?)\s*%", low) or
            re.search(r"(\d+(?:\.\d+)?)\s*%\s*(?:of\s*(?:standard|normal|expected|baseline|usual)?\s*(?:output|generation|capacity|solar|pv))", low)
        )
        if m_remain:
            factor = round(float(m_remain.group(1)) / 100.0, 4)
        elif "half" in low:
            factor = 0.5
        else:
            m_red = (
                re.search(r"(\d+(?:\.\d+)?)\s*%\s*(?:reduction|fall|drop|cut|loss)", low) or
                re.search(r"(?:fall|drop|reduce|cut|curtail|decrease)\s*by\s*(\d+(?:\.\d+)?)\s*%", low)
            )
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

def _get_system_prompt() -> str:
    return """
You are an expert energy operator interpreting shift notes into strict structured JSON directives.
There are EXACTLY 6 allowed directive types:
1. `solar_reduction`: usable solar drops. Shape: {"hours": [...], "factor": 0..1}. 'factor' is the fraction REMAINING. e.g. "80% reduction" -> factor=0.2. "drops to 20%" -> factor=0.2.
2. `minimum_battery_reserve`: keep battery >= X. Shape: {"hours": [...], "minimum_energy_kwh": n}. If note specifies a percentage of battery capacity, multiply by the given battery capacity.
3. `no_charge_window`: can't charge. Shape: {"hours": [...]}.
4. `no_discharge_window`: can't discharge. Shape: {"hours": [...]}.
5. `max_grid_window`: grid import cap. Shape: {"hours": [...], "max_grid_kwh": n}.
6. `no_op`: irrelevant note. Shape: null. Use this for notes about menus, deadlines, bookings, announcements, etc.

Rules:
- You must output a JSON object with a single key "directives" containing a list of exactly `note_count` objects.
- Each object must match the DirectiveInterpretation schema: `{"note_index": int, "applies": bool, "directive_type": str, "structured_adjustment": dict|null, "explanation": str}`.
- For `no_op`, `applies` must be false and `structured_adjustment` must be null.
- For all other types, `applies` must be true and `structured_adjustment` must exactly match the required shape for that type.
- Time phrases are start-inclusive, end-exclusive. "1 PM to 3 PM" -> hours [13, 14]. "midnight to 2am" -> [0, 1]. "14:00 to 16:00" -> [14, 15].
- Never modify base demand, tariff, or battery base parameters. Only use the 5 adjustment types.
- If a note does not fit the 5 types exactly, mark it `no_op`.

Few-shot examples (study these carefully to see paraphrasing robustness):
Example 1:
Note 0: "Maintenance on grid tie from 10am to 12pm, import capped at 50 kWh."
Output: {"note_index": 0, "applies": true, "directive_type": "max_grid_window", "structured_adjustment": {"hours": [10, 11], "max_grid_kwh": 50}, "explanation": "Grid import capped at 50kWh during 10am to 12pm maintenance"}

Example 2:
Note 0: "Rooftop PV output will fall by 60% due to cleaning between 13:00 and 15:00."
Output: {"note_index": 0, "applies": true, "directive_type": "solar_reduction", "structured_adjustment": {"hours": [13, 14], "factor": 0.4}, "explanation": "60% fall leaves 40% remaining factor during 13:00-15:00"}

Example 3:
Note 0: "Keep at least 50% of the battery capacity stored in the battery from 6 PM until 9 PM for emergency operations." (Capacity = 200 kWh)
Output: {"note_index": 0, "applies": true, "directive_type": "minimum_battery_reserve", "structured_adjustment": {"hours": [18, 19, 20], "minimum_energy_kwh": 100}, "explanation": "50% of 200 kWh capacity is 100 kWh minimum reserve"}

Example 4:
Note 0: "Battery offline for discharging between 2am and 5am."
Output: {"note_index": 0, "applies": true, "directive_type": "no_discharge_window", "structured_adjustment": {"hours": [2, 3, 4]}, "explanation": "Discharge offline 02:00-05:00"}

Example 5:
Note 0: "Do not charge the ESS from 8 AM to 10 AM."
Output: {"note_index": 0, "applies": true, "directive_type": "no_charge_window", "structured_adjustment": {"hours": [8, 9]}, "explanation": "Charging blocked 08:00-10:00"}

Example 6:
Note 0: "Reminder: Town hall meeting in the cafeteria at 2 PM, coffee provided."
Output: {"note_index": 0, "applies": false, "directive_type": "no_op", "structured_adjustment": null, "explanation": "Unrelated announcement"}

Process the following notes and return the strictly formatted JSON list inside {"directives": [...]}.
"""

_client = None

def get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("LLM_API_KEY")
        base_url = os.environ.get("LLM_BASE_URL")
        provider = os.environ.get("LLM_PROVIDER", "").lower()
        
        if not base_url and api_key:
            if provider == "gemini" or api_key.startswith("AQ.") or api_key.startswith("AIzaSy"):
                base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
                
        if api_key:
            if base_url:
                _client = OpenAI(api_key=api_key, base_url=base_url)
            else:
                _client = OpenAI(api_key=api_key)
    return _client

def interpret_notes(notes: List[str], scenario_id: str, battery_capacity_kwh: float = 500.0) -> List[dict]:
    """
    Takes a list of operator notes, checks cache, and calls LLM (or robust heuristic fallback) for misses.
    Returns a list of raw dicts corresponding to each note_index.
    """
    results: List[Optional[dict]] = [None] * len(notes)
    misses: List[tuple[int, str]] = []
    
    # 1. Check cache
    for i, note in enumerate(notes):
        norm = normalize_text(note)
        if norm in _NOTE_CACHE:
            logger.info(f"[{scenario_id}] Cache hit for note {i}")
            cached_result = _NOTE_CACHE[norm].copy()
            cached_result["note_index"] = i
            results[i] = cached_result
        else:
            misses.append((i, note))
            
    # 2. Call LLM for misses if API key configured
    if misses:
        model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
        client = get_client()
        
        if client:
            prompt = f"Battery Capacity: {battery_capacity_kwh} kWh\nNotes to interpret:\n"
            for i, note in misses:
                prompt += f"Note {i}: {note}\n"
                
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": _get_system_prompt()},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    timeout=10.0
                )
                raw_text = response.choices[0].message.content
                parsed = json.loads(raw_text)
                
                if isinstance(parsed, dict):
                    new_directives = parsed.get("directives", [])
                elif isinstance(parsed, list):
                    new_directives = parsed
                else:
                    new_directives = []
                
                for d in new_directives:
                    idx = d.get("note_index")
                    if isinstance(idx, int) and 0 <= idx < len(notes) and results[idx] is None:
                        results[idx] = d
                        orig_note = notes[idx]
                        _NOTE_CACHE[normalize_text(orig_note)] = d
                        logger.info(f"[{scenario_id}] Successfully extracted directive for note {idx} via Primary Model")
                        
            except Exception as e:
                logger.warning(f"[{scenario_id}] Primary LLM call failed ({e}). Attempting Fallback Model...")
                fallback_model = os.environ.get("FALLBACK_LLM_MODEL")
                if fallback_model:
                    try:
                        fb_response = client.chat.completions.create(
                            model=fallback_model,
                            messages=[
                                {"role": "system", "content": _get_system_prompt()},
                                {"role": "user", "content": prompt}
                            ],
                            response_format={"type": "json_object"},
                            timeout=10.0
                        )
                        fb_raw_text = fb_response.choices[0].message.content
                        fb_parsed = json.loads(fb_raw_text)
                        
                        if isinstance(fb_parsed, dict):
                            new_directives = fb_parsed.get("directives", [])
                        elif isinstance(fb_parsed, list):
                            new_directives = fb_parsed
                        else:
                            new_directives = []
                            
                        for d in new_directives:
                            idx = d.get("note_index")
                            if isinstance(idx, int) and 0 <= idx < len(notes) and results[idx] is None:
                                results[idx] = d
                                orig_note = notes[idx]
                                _NOTE_CACHE[normalize_text(orig_note)] = d
                                logger.info(f"[{scenario_id}] Successfully extracted directive for note {idx} via Fallback Model")
                    except Exception as fb_e:
                        logger.error(f"[{scenario_id}] Fallback LLM call failed: {fb_e}")

    # 3. Deterministic rule-based fallback for any missing or un-extracted notes
    for i in range(len(notes)):
        if results[i] is None:
            logger.info(f"[{scenario_id}] Applying deterministic rule-based extractor for note {i}")
            extracted = extract_rule_directive(notes[i], i, battery_capacity_kwh)
            results[i] = extracted
            _NOTE_CACHE[normalize_text(notes[i])] = extracted
            
    return results
