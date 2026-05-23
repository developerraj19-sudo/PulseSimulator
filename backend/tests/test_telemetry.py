import unittest
from app.services.telemetry import apply_vital_tick, INTERVENTION_REGISTRY

class TestTelemetryEngine(unittest.TestCase):
    def test_anaphylaxis_degradation(self):
        """Tests that anaphylaxis patient vitals deteriorate correctly over time."""
        state = {
            "case_id": "case_anaphylaxis_001",
            "elapsed_seconds": 0,
            "simulated_minutes": 0,
            "vitals_hr": 115.0,
            "vitals_bps": 88.0,
            "vitals_bpd": 52.0,
            "vitals_spo2": 90.0,
            "vitals_temp": 36.8,
            "anxiety": 95.0,
            "stabilized": False,
            "active_treatments": []
        }

        # Tick 10 seconds
        for _ in range(10):
            state = apply_vital_tick(state)

        # Heart rate should go UP (base rate +0.4/s)
        self.assertGreater(state["vitals_hr"], 115.0)
        # Blood pressure Systolic should go DOWN (base rate -0.35/s)
        self.assertLess(state["vitals_bps"], 88.0)
        # SpO2 should go DOWN (base rate -0.25/s)
        self.assertLess(state["vitals_spo2"], 90.0)
        # Anxiety should go UP (base rate +0.6/s)
        self.assertGreater(state["anxiety"], 95.0)

    def test_vital_capping_limits(self):
        """Tests that vitals do not exceed physiological limits."""
        state = {
            "case_id": "case_anaphylaxis_001",
            "elapsed_seconds": 0,
            "simulated_minutes": 0,
            "vitals_hr": 178.0,
            "vitals_bps": 50.0,
            "vitals_bpd": 30.0,
            "vitals_spo2": 42.0,
            "vitals_temp": 36.8,
            "anxiety": 99.0,
            "stabilized": False,
            "active_treatments": []
        }

        # Tick 20 times. Limits should cap the values
        for _ in range(20):
            state = apply_vital_tick(state)

        self.assertEqual(state["vitals_hr"], 180.0)      # Max cap
        self.assertEqual(state["vitals_bps"], 45.0)      # Min cap
        self.assertEqual(state["vitals_spo2"], 40.0)     # Min cap
        self.assertEqual(state["anxiety"], 100.0)         # Max cap

    def test_epinephrine_stabilization(self):
        """Tests that administering Epinephrine reverses the deterioration in Anaphylaxis."""
        state = {
            "case_id": "case_anaphylaxis_001",
            "elapsed_seconds": 0,
            "simulated_minutes": 0,
            "vitals_hr": 115.0,
            "vitals_bps": 88.0,
            "vitals_bpd": 52.0,
            "vitals_spo2": 90.0,
            "vitals_temp": 36.8,
            "anxiety": 95.0,
            "stabilized": False,
            "active_treatments": []
        }

        # Apply epinephrine IM intervention
        epi = INTERVENTION_REGISTRY["epinephrine_im"]
        state["active_treatments"].append({
            "name": "epinephrine_im",
            "start_elapsed": state["elapsed_seconds"],
            "duration": epi["effect_duration"],
            "effects": epi["effects"]
        })

        # Tick 20 seconds. Let the drug work.
        for _ in range(20):
            state = apply_vital_tick(state)

        # Net rate for HR should be 0.4 + (-0.5) = -0.1 (decreasing towards normal)
        self.assertLess(state["vitals_hr"], 115.0)
        # Net rate for BPS should be -0.35 + 0.6 = +0.25 (recovering)
        self.assertGreater(state["vitals_bps"], 88.0)
        # Net rate for SpO2 should be -0.25 + 0.45 = +0.2 (recovering)
        self.assertGreater(state["vitals_spo2"], 90.0)
        # Net rate for Anxiety should be 0.6 + (-0.7) = -0.1 (recovering)
        self.assertLess(state["anxiety"], 95.0)

if __name__ == "__main__":
    unittest.main()
