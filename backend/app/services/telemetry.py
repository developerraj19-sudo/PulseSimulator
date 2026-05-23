import logging
import time
from typing import Dict, Any, List

logger = logging.getLogger("telemetry")

# --- Clinical Constants & Limits ---
VITALS_LIMITS = {
    "vitals_hr": {"min": 30.0, "max": 180.0, "normal": 72.0},
    "vitals_bps": {"min": 45.0, "max": 210.0, "normal": 120.0},
    "vitals_bpd": {"min": 25.0, "max": 130.0, "normal": 80.0},
    "vitals_spo2": {"min": 40.0, "max": 100.0, "normal": 99.0},
    "vitals_temp": {"min": 34.0, "max": 42.0, "normal": 37.0},
    "anxiety": {"min": 0.0, "max": 100.0, "normal": 20.0}
}

# --- Base Case Degradation Rates (per second) ---
BASE_DEGRADATION_RATES = {
    "case_anaphylaxis_001": {
        "vitals_hr": 0.4,       # Tachycardia
        "vitals_bps": -0.35,    # Hypotension
        "vitals_bpd": -0.25,    # Hypotension
        "vitals_spo2": -0.25,   # Hypoxia (very dangerous!)
        "vitals_temp": 0.0,     # Stable temp
        "anxiety": 0.6          # High panic
    },
    "case_appendicitis_001": {
        "vitals_hr": 0.04,      # Mild tachycardia from fever/pain
        "vitals_bps": -0.02,    # Slow shock if untreated
        "vitals_bpd": -0.01,
        "vitals_spo2": 0.0,     # Normal respiratory function
        "vitals_temp": 0.001,   # Rising fever
        "anxiety": 0.08         # Pain anxiety
    }
}

# --- Standardized Database of Interventions ---
INTERVENTION_REGISTRY = {
    # Medications
    "epinephrine_im": {
        "display_name": "Epinephrine 0.3mg IM",
        "cost": 50.00,
        "time_penalty_minutes": 1,
        "effects": {
            "vitals_hr": -0.5,    # counteracts anaphylaxis tachycardia
            "vitals_bps": 0.6,    # vasoconstriction raises BP
            "vitals_bpd": 0.4,
            "vitals_spo2": 0.45,  # bronchodilation improves oxygenation
            "anxiety": -0.7
        },
        "effect_duration": 180 # seconds (3 minutes)
    },
    "albuterol_neb": {
        "display_name": "Albuterol Nebulizer 2.5mg",
        "cost": 30.00,
        "time_penalty_minutes": 10,
        "effects": {
            "vitals_hr": 0.15,    # beta-agonist raises HR slightly as side effect
            "vitals_spo2": 0.3,   # bronchodilation
            "anxiety": -0.2
        },
        "effect_duration": 120
    },
    "methylprednisolone_iv": {
        "display_name": "IV Methylprednisolone 125mg",
        "cost": 45.00,
        "time_penalty_minutes": 15,
        "effects": {
            "vitals_bps": 0.1,
            "vitals_spo2": 0.15,
            "anxiety": -0.1
        },
        "effect_duration": 300
    },
    "normal_saline_iv": {
        "display_name": "IV Normal Saline 1L Bolus",
        "cost": 80.00,
        "time_penalty_minutes": 15,
        "effects": {
            "vitals_hr": -0.1,    # volume expansion slows compensatory tachycardia
            "vitals_bps": 0.25,   # volume expands blood pressure
            "vitals_bpd": 0.15
        },
        "effect_duration": 240
    },
    "morphine_iv": {
        "display_name": "IV Morphine 4mg",
        "cost": 40.00,
        "time_penalty_minutes": 5,
        "effects": {
            "vitals_hr": -0.15,   # analgesia lowers sympathetic drive
            "vitals_bps": -0.05,  # vasodilating side effect lowers BP slightly
            "anxiety": -0.5
        },
        "effect_duration": 200
    },
    "piperacillin_tazobactam_iv": {
        "display_name": "IV Piperacillin/Tazobactam 3.375g",
        "cost": 120.00,
        "time_penalty_minutes": 30,
        "effects": {
            "vitals_temp": -0.003, # antibiotic treats source of fever
            "vitals_hr": -0.05,
            "anxiety": -0.1
        },
        "effect_duration": 400
    },
    
    # Diagnostics & Imaging
    "complete_blood_count": {
        "display_name": "Complete Blood Count (CBC)",
        "cost": 65.00,
        "time_penalty_minutes": 20,
        "effects": {},
        "effect_duration": 0
    },
    "comprehensive_metabolic_panel": {
        "display_name": "Comprehensive Metabolic Panel (CMP)",
        "cost": 85.00,
        "time_penalty_minutes": 30,
        "effects": {},
        "effect_duration": 0
    },
    "arterial_blood_gas": {
        "display_name": "Arterial Blood Gas (ABG)",
        "cost": 110.00,
        "time_penalty_minutes": 10,
        "effects": {},
        "effect_duration": 0
    },
    "abdominal_ultrasound": {
        "display_name": "Abdominal Ultrasound",
        "cost": 220.00,
        "time_penalty_minutes": 45,
        "effects": {},
        "effect_duration": 0
    },
    "abdominal_ct": {
        "display_name": "Abdominal CT Scan with IV Contrast",
        "cost": 550.00,
        "time_penalty_minutes": 60,
        "effects": {},
        "effect_duration": 0
    },
    "chest_xray": {
        "display_name": "Chest X-Ray (1-view)",
        "cost": 120.00,
        "time_penalty_minutes": 15,
        "effects": {},
        "effect_duration": 0
    },
    
    # Consultations
    "surgical_consult": {
        "display_name": "Surgical Consultation",
        "cost": 300.00,
        "time_penalty_minutes": 15,
        "effects": {
            "anxiety": -0.3 # reassures patient
        },
        "effect_duration": 60
    }
}

def apply_vital_tick(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes vital sign degradation or recovery for a single simulation second.
    """
    case_id = state.get("case_id")
    elapsed = state.get("elapsed_seconds", 0)
    
    # Increment times
    state["elapsed_seconds"] = elapsed + 1
    
    # Fetch base rates
    base_rates = BASE_DEGRADATION_RATES.get(case_id, {
        "vitals_hr": 0.0, "vitals_bps": 0.0, "vitals_bpd": 0.0, 
        "vitals_spo2": 0.0, "vitals_temp": 0.0, "anxiety": 0.0
    }).copy()
    
    # Calculate compound rates based on active treatments
    active_treatments = state.get("active_treatments", [])
    valid_treatments = []
    
    for tx in active_treatments:
        start_time = tx.get("start_elapsed", 0)
        duration = tx.get("duration", 0)
        
        # Check if the treatment is still active
        if (state["elapsed_seconds"] - start_time) < duration:
            valid_treatments.append(tx)
            # Add drug properties to the net rate of change
            effects = tx.get("effects", {})
            for key, val in effects.items():
                if key in base_rates:
                    base_rates[key] += val
        else:
            logger.debug(f"Treatment {tx.get('name')} has expired.")

    state["active_treatments"] = valid_treatments
    
    # Mutate state vitals based on rates
    for vital, rate in base_rates.items():
        current_val = state.get(vital, VITALS_LIMITS[vital]["normal"])
        new_val = current_val + rate
        
        # Clip within safety/physiological ranges
        v_min = VITALS_LIMITS[vital]["min"]
        v_max = VITALS_LIMITS[vital]["max"]
        state[vital] = round(max(v_min, min(new_val, v_max)), 2)

    # Check for stabilization condition
    check_stabilization(state)
    
    return state

def check_stabilization(state: Dict[str, Any]) -> None:
    """
    Updates the 'stabilized' flag in state based on diagnostic thresholds.
    """
    case_id = state.get("case_id")
    
    # Anaphylaxis is stabilized if epinephrine was given and SpO2 + BP are recovering
    if case_id == "case_anaphylaxis_001":
        has_epi = any(tx.get("name") == "epinephrine_im" for tx in state.get("active_treatments", []))
        if has_epi and state.get("vitals_spo2", 0) >= 94.0 and state.get("vitals_bps", 0) >= 100.0:
            state["stabilized"] = True
            return
            
    # Appendicitis is stabilized if antibiotics, IV fluid, and morphine were given
    elif case_id == "case_appendicitis_001":
        has_abx = any(tx.get("name") == "piperacillin_tazobactam_iv" for tx in state.get("active_treatments", []))
        has_fluids = any(tx.get("name") == "normal_saline_iv" for tx in state.get("active_treatments", []))
        has_pain_med = any(tx.get("name") == "morphine_iv" for tx in state.get("active_treatments", []))
        if has_abx and has_fluids and has_pain_med:
            state["stabilized"] = True
            return

    state["stabilized"] = False
