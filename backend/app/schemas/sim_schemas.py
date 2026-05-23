from pydantic import BaseModel, EmailStr, Field
from typing import List, Dict, Any, Optional

class SimulationStart(BaseModel):
    user_email: EmailStr = Field(..., description="Email address of the student")
    case_id: str = Field(..., description="ID of the clinical case (e.g. case_anaphylaxis_001)")

class InterventionRequest(BaseModel):
    intervention_id: str = Field(..., description="Identifier of the intervention from the registry")

class InterventionResponse(BaseModel):
    success: bool
    display_name: str
    cost: float
    time_penalty_minutes: int
    new_simulated_minutes: int
    message: str

class ChatMessage(BaseModel):
    message: str = Field(..., description="Text content sent by the student")

class VitalsState(BaseModel):
    sim_id: str
    case_id: str
    status: str
    elapsed_seconds: int
    simulated_minutes: int
    vitals_hr: float
    vitals_bps: float
    vitals_bpd: float
    vitals_spo2: float
    vitals_temp: float
    anxiety: float
    stabilized: bool
    budget_remaining: float

class SimulationSummary(BaseModel):
    sim_id: str
    user_email: str
    case_id: str
    status: str
    total_cost: float
    elapsed_seconds: int
    chat_count: int
    intervention_count: int
