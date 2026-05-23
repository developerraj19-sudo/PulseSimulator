import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.agent import fallback_router, fallback_persona, fallback_grader, agent_graph

class TestLangGraphAgent(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_fallback_router(self):
        # Test routing strings
        self.assertEqual(fallback_router("Where does it hurt?"), "inquiry")
        self.assertEqual(fallback_router("Please describe the pain"), "inquiry")
        
        self.assertEqual(fallback_router("Give 0.3mg Epinephrine IM"), "intervention")
        self.assertEqual(fallback_router("Let's order a CT scan of the abdomen"), "intervention")
        
        self.assertEqual(fallback_router("Diagnose as appendicitis"), "submission")
        self.assertEqual(fallback_router("My final diagnosis is anaphylactic shock"), "submission")

    def test_fallback_persona_inquiry_symptom(self):
        # Test symptom response matching
        symptom_ctx = {
            "body_part": "lower abdomen",
            "baseline_severity": 8
        }
        res = fallback_persona("Does your belly hurt?", symptom_ctx, 40.0, "Appendicitis")
        self.assertIn("lower abdomen", res)
        self.assertIn("8 out of 10", res)

    def test_fallback_persona_distressed(self):
        # High anxiety should trigger distressed markers
        res = fallback_persona("What happened?", None, 85.0, "Anaphylaxis")
        self.assertIn("help me", res)
        self.assertIn("doctor", res)

    def test_fallback_grader(self):
        logs = {
            "diagnosis_submitted": "My diagnosis is anaphylaxis",
            "chat_transcript": ["student: How are you?", "patient: I can't breathe"],
            "interventions_done": ["Epinephrine 0.3mg IM (Cost: $50.00)"]
        }
        report = fallback_grader(logs, "Anaphylaxis")
        self.assertEqual(report.accuracy, 1.0)
        self.assertGreaterEqual(report.resource, 0.8)
        self.assertIn("Total interventions cost", report.feedback)

    @patch("app.db.redis_client.redis_client.get_simulation_state", new_callable=AsyncMock)
    @patch("app.db.neo4j_client.neo4j_client.fetch_case_by_id", new_callable=AsyncMock)
    @patch("app.db.neo4j_client.neo4j_client.check_symptom_exists", new_callable=AsyncMock)
    def test_full_graph_routing_and_execution(self, mock_symptom, mock_case, mock_redis):
        # Setup mocks
        mock_redis.return_value = {
            "case_id": "case_anaphylaxis_001",
            "vitals_hr": 110,
            "vitals_bps": 85,
            "vitals_bpd": 50,
            "vitals_spo2": 90,
            "vitals_temp": 37.0,
            "anxiety": 80.0,
            "total_spent": 50.0,
            "budget": 1000.0,
            "elapsed_seconds": 15,
            "simulated_minutes": 5,
            "status": "running"
        }
        
        mock_case.return_value = {
            "case": {
                "title": "Respiratory Distress / Anaphylaxis",
                "difficulty": "Hard",
                "patient_age": 28,
                "patient_gender": "Female",
                "patient_personality": "Distressed and anxious"
            },
            "disease": {"name": "Anaphylaxis"},
            "symptoms": [{"name": "Chest Tightness"}]
        }
        
        mock_symptom.return_value = {
            "name": "Chest Tightness",
            "body_part": "chest",
            "baseline_severity": 7
        }

        # Invoke Graph for Chat Inquiry
        state_in = {
            "sim_id": "test_sim_uuid",
            "user_input": "Is your chest feeling tight?",
            "input_type": "inquiry",
            "case_id": "case_anaphylaxis_001",
            "vitals": {},
            "neo4j_context": {},
            "patient_response": "",
            "grading_result": {}
        }
        
        async def run_test():
            return await agent_graph.ainvoke(state_in)

        state_out = self.loop.run_until_complete(run_test())
        self.assertEqual(state_out["input_type"], "inquiry")
        self.assertIn("chest", state_out["patient_response"])

if __name__ == "__main__":
    unittest.main()
