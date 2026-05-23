import json
import logging
import re
from typing import Dict, Any, List, Literal
from typing_extensions import TypedDict
from pydantic import BaseModel, Field

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END

from app.config import settings
from app.db.neo4j_client import neo4j_client
from app.db.redis_client import redis_client
from app.db.postgres_client import postgres_client

logger = logging.getLogger("agent")

# --- Define Agent State ---
class AgentState(TypedDict):
    sim_id: str
    user_input: str
    input_type: Literal["inquiry", "intervention", "submission"]
    case_id: str
    vitals: Dict[str, Any]
    neo4j_context: Dict[str, Any]
    patient_response: str
    grading_result: Dict[str, Any]

# --- Router Structured Output Model ---
class RouteDecision(BaseModel):
    input_type: Literal["inquiry", "intervention", "submission"] = Field(
        description="The classification of the student's message"
    )

# --- Grader Structured Output Model ---
class EvaluationReport(BaseModel):
    accuracy: float = Field(description="Diagnostic accuracy score from 0.0 to 1.0")
    empathy: float = Field(description="Bedside manner and empathy score from 0.0 to 1.0")
    resource: float = Field(description="Financial and resource efficiency score from 0.0 to 1.0")
    feedback: str = Field(description="Detailed feedback summarizing accomplishments and blind spots")

# --- Node 1: InputRouter ---
async def router_node(state: AgentState) -> Dict[str, Any]:
    """
    Classifies the user input into Inquiry, Intervention, or Diagnostic Submission.
    """
    user_input = state["user_input"]
    
    # Fallback/Mock check — covers both mock-key default and unset placeholder from .env
    _key = settings.OPENAI_API_KEY or ""
    if not _key or _key in ("mock-key", "your_openai_api_key_here"):
        return {"input_type": fallback_router(user_input)}
        
    try:
        llm = ChatOpenAI(model="gpt-4o", temperature=0, openai_api_key=settings.OPENAI_API_KEY)
        structured_llm = llm.with_structured_output(RouteDecision)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert clinical classifier. Classify the medical student's text input.\n"
                       "Choose 'inquiry' if they are asking questions about symptoms, history, pain, or general status.\n"
                       "Choose 'intervention' if they are verbally ordering a drug, fluid, scan, lab, or consultant.\n"
                       "Choose 'submission' if they are explicitly submitting a final diagnosis to end the case."),
            ("user", "{user_input}")
        ])
        
        chain = prompt | structured_llm
        decision = await chain.ainvoke({"user_input": user_input})
        return {"input_type": decision.input_type}
    except Exception as e:
        logger.error(f"Router LLM invocation failed: {e}. Defaulting to regex fallback.")
        return {"input_type": fallback_router(user_input)}

def fallback_router(text: str) -> str:
    text_lower = text.lower()
    
    # Submission checks
    if any(k in text_lower for k in ["diagnose", "diagnosis", "submit", "final", "my diagnosis is", "code red"]):
        return "submission"
    # Intervention checks
    if any(k in text_lower for k in ["give", "administer", "infuse", "order", "scan", "iv", "inject", "epinephrine", "saline", "morphine"]):
        return "intervention"
    
    return "inquiry"

# --- Node 2: ContextFetcher ---
async def context_fetcher_node(state: AgentState) -> Dict[str, Any]:
    """
    Retrieves the clinical history constraints from Neo4j and live telemetry from Redis.
    """
    sim_id = state["sim_id"]
    user_input = state["user_input"]
    
    # 1. Fetch live telemetry from Redis
    vitals = await redis_client.get_simulation_state(sim_id)
    case_id = vitals.get("case_id") if vitals else state.get("case_id", "case_anaphylaxis_001")
    
    # 2. Query Neo4j Case Metadata
    case_data = await neo4j_client.fetch_case_by_id(case_id)
    
    # 3. Check for specific symptom inquiries to prevent hallucination
    # Extract keywords
    words = re.findall(r"\b\w{4,}\b", user_input.lower())
    matched_symptom = None
    for word in words:
        symptom_data = await neo4j_client.check_symptom_exists(case_id, word)
        if symptom_data:
            matched_symptom = symptom_data
            break
            
    neo4j_context = {
        "case_metadata": case_data.get("case", {}) if case_data else {},
        "disease_metadata": case_data.get("disease", {}) if case_data else {},
        "matched_symptom": matched_symptom
    }
    
    return {
        "case_id": case_id,
        "vitals": vitals or {},
        "neo4j_context": neo4j_context
    }

# --- Node 3: PersonaEngine ---
async def persona_engine_node(state: AgentState) -> Dict[str, Any]:
    """
    Synthesizes dialogue strictly conforming to case constraints and anxiety levels.
    """
    user_input = state["user_input"]
    vitals = state["vitals"]
    context = state["neo4j_context"]
    
    metadata = context.get("case_metadata", {})
    age = metadata.get("patient_age", 30)
    gender = metadata.get("patient_gender", "Unknown")
    personality = metadata.get("patient_personality", "Polite and responsive.")
    
    anxiety = vitals.get("anxiety", 40.0)
    hr = vitals.get("vitals_hr", 72.0)
    bps = vitals.get("vitals_bps", 120.0)
    bpd = vitals.get("vitals_bpd", 80.0)
    spo2 = vitals.get("vitals_spo2", 98.0)
    temp = vitals.get("vitals_temp", 37.0)
    
    matched_symptom = context.get("matched_symptom")
    symptom_str = "No specific symptom matched in user inquiry."
    if matched_symptom:
        symptom_str = (
            f"Symptom: {matched_symptom.get('name')}, "
            f"body part: {matched_symptom.get('body_part')}, "
            f"severity: {matched_symptom.get('baseline_severity')}/10"
        )
    
    # Fallback/Mock check — covers both mock-key default and unset placeholder from .env
    _key = settings.OPENAI_API_KEY or ""
    if not _key or _key in ("mock-key", "your_openai_api_key_here"):
        return {"patient_response": fallback_persona(user_input, matched_symptom, anxiety, current_case_title(state["case_id"]))}

    try:
        llm = ChatOpenAI(model="gpt-4o", temperature=0.6, openai_api_key=settings.OPENAI_API_KEY)
        
        system_prompt = (
            f"You are a patient in a medical simulation. You must adopt the following persona:\n"
            f"- Age: {age}\n"
            f"- Gender: {gender}\n"
            f"- Personality/State: {personality}\n"
            f"- Anxiety Score: {anxiety}/100\n\n"
            f"Your current physiological vitals are:\n"
            f"- Heart Rate: {hr} bpm\n"
            f"- Blood Pressure: {bps}/{bpd} mmHg\n"
            f"- SpO2: {spo2}%\n"
            f"- Temperature: {temp} °C\n\n"
            f"Here is the strict clinical truth about your symptoms:\n"
            f"- Matches symptom: {symptom_str}\n\n"
            f"CRITICAL DIRECTIVES:\n"
            f"1. Zero Hallucination: Do NOT invent symptoms, labs, or history. If the student asks about a symptom not "
            f"found in the matched symptom above, state in-character that you feel fine there, or that the symptom is not present.\n"
            f"2. Partition of emotions: If your anxiety is high (>75%), speak with distress, panic, and short sentences.\n"
            f"3. Speak directly as the patient. Do not add narrative text or actions (like *groans*)."
        )
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "{user_input}")
        ])
        
        chain = prompt | llm
        response = await chain.ainvoke({"user_input": user_input})
        return {"patient_response": response.content}
    except Exception as e:
        logger.error(f"Persona LLM invocation failed: {e}. Defaulting to rule-based dialogue.")
        return {"patient_response": fallback_persona(user_input, matched_symptom, anxiety, current_case_title(state["case_id"]))}

def fallback_persona(text: str, symptom: Any, anxiety: float, case_title: str) -> str:
    distressed = anxiety > 75.0
    text_lower = text.lower()
    
    if distressed:
        prefix = "Ugh... ah... doctor... "
        suffix = "... help me..."
    else:
        prefix = ""
        suffix = ""

    if symptom:
        return f"{prefix}Yes, my {symptom['body_part']} is hurting. The pain is about a {symptom['baseline_severity']} out of 10.{suffix}"
        
    if "allergy" in text_lower or "allergies" in text_lower:
        if "anaphylaxis" in case_title.lower():
            return f"{prefix}I think... I ate a peanut cookie... a few minutes ago... throat is tight...{suffix}"
        return "No, I don't think I have any allergies."
        
    if "pain" in text_lower or "hurt" in text_lower:
        if "anaphylaxis" in case_title.lower():
            return f"{prefix}Just chest tightness... and my skin is itching so bad...{suffix}"
        return f"{prefix}My lower stomach hurts a lot, especially when I move.{suffix}"
        
    return f"{prefix}I'm just feeling really scared and unwell...{suffix}"

# --- Node 4: EvaluationEngine ---
async def evaluation_engine_node(state: AgentState) -> Dict[str, Any]:
    """
    Grades the student transcript and audit logs against a clinical rubric.
    """
    sim_id = state["sim_id"]
    case_id = state["case_id"]
    user_input = state["user_input"]
    
    # 1. Fetch simulation records from PostgreSQL
    summary = await postgres_client.get_simulation_summary(sim_id)
    chat_logs = summary.get("chat_logs", [])
    interventions = summary.get("interventions", [])
    
    # Determine case truth variables
    case_data = await neo4j_client.fetch_case_by_id(case_id)
    disease_name = case_data["disease"]["name"] if case_data else "Unknown Case"
    
    # Compile log context
    logs_context = {
        "diagnosis_submitted": user_input,
        "chat_transcript": [f"{c['speaker']}: {c['transcript']}" for c in chat_logs],
        "interventions_done": [f"{i['action_taken']} (Cost: ${i['cost_incurred']})" for i in interventions]
    }
    
    # Fallback/Mock check — covers both mock-key default and unset placeholder from .env
    _key = settings.OPENAI_API_KEY or ""
    if not _key or _key in ("mock-key", "your_openai_api_key_here"):
        return {"grading_result": fallback_grader(logs_context, disease_name).model_dump()}

    try:
        llm = ChatOpenAI(model="gpt-4o", temperature=0, openai_api_key=settings.OPENAI_API_KEY)
        structured_llm = llm.with_structured_output(EvaluationReport)
        
        system_prompt = (
            f"You are a senior medical professor grading a clinical simulation.\n"
            f"Case Disease: {disease_name}\n\n"
            f"Grading Rubric:\n"
            f"1. Diagnostic Accuracy (0.0 to 1.0): Check if the submitted diagnosis matches the Case Disease.\n"
            f"2. Bedside Manner / Empathy (0.0 to 1.0): Empathy and tone of the student in the chat history.\n"
            f"3. Resource Efficiency (0.0 to 1.0): Optimal actions (Anaphylaxis: Epinephrine. Appendicitis: Surgical consult, fluids, antibiotics). Penalize redundant labs/imaging.\n\n"
            f"Return a structured evaluation JSON containing the criteria grades and summary feedback."
        )
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "Evaluate these simulation records:\n{logs_context}")
        ])
        
        chain = prompt | structured_llm
        report = await chain.ainvoke({"logs_context": json.dumps(logs_context)})
        return {"grading_result": report.model_dump()}
    except Exception as e:
        logger.error(f"Grader LLM invocation failed: {e}. Defaulting to rule-based scoring.")
        return {"grading_result": fallback_grader(logs_context, disease_name).model_dump()}

def fallback_grader(logs: Dict[str, Any], true_disease: str) -> EvaluationReport:
    sub = logs["diagnosis_submitted"].lower()
    
    # Accuracy score
    accuracy = 0.0
    if true_disease.lower() == "anaphylaxis" and ("anaphylaxis" in sub or "anaphylactic" in sub or "allergic" in sub):
        accuracy = 1.0
    elif true_disease.lower() == "acute appendicitis" and ("appendicitis" in sub or "appendix" in sub):
        accuracy = 1.0
    elif "appendicitis" in sub or "anaphylaxis" in sub:
        accuracy = 0.5
        
    # Empathy score
    empathy = 0.85
    
    # Resource score — parse cost from intervention strings like "Drug Name (Cost: $50.0)"
    cost = 0.0
    for item in logs["interventions_done"]:
        if "$" in item:
            try:
                cost += float(item.split("$")[1].rstrip(")").strip())
            except (ValueError, IndexError):
                pass
    resource = max(0.2, min(1.0, 1.0 - (cost / 1000.0)))
    
    feedback = (
        f"Student submitted diagnosis: '{logs['diagnosis_submitted']}'. "
        f"The correct disease was {true_disease}. "
        f"Total interventions cost incurred was ${cost:.2f}."
    )
    
    return EvaluationReport(
        accuracy=accuracy,
        empathy=empathy,
        resource=resource,
        feedback=feedback
    )

# --- Compile Graph ---
def create_agent_graph() -> StateGraph:
    workflow = StateGraph(AgentState)
    
    # Add Nodes
    workflow.add_node("router", router_node)
    workflow.add_node("context_fetcher", context_fetcher_node)
    workflow.add_node("persona_engine", persona_engine_node)
    workflow.add_node("evaluation_engine", evaluation_engine_node)
    
    # Set Entry Point
    workflow.set_entry_point("router")
    
    # Define Conditional Edge
    def route_decision_edge(state: AgentState) -> str:
        if state["input_type"] == "submission":
            return "evaluation"
        return "inquiry"

    workflow.add_conditional_edges(
        "router",
        route_decision_edge,
        {
            "evaluation": "evaluation_engine",
            "inquiry": "context_fetcher"
        }
    )
    
    # Add Sequential Edges
    workflow.add_edge("context_fetcher", "persona_engine")
    workflow.add_edge("persona_engine", END)
    workflow.add_edge("evaluation_engine", END)
    
    return workflow.compile()

# Instantiate compiled graph
agent_graph = create_agent_graph()

# --- Helper Methods ---
def current_case_title(case_id: str) -> str:
    if case_id == "case_anaphylaxis_001":
        return "Anaphylaxis"
    return "Acute Appendicitis"
