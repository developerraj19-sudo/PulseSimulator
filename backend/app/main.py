import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.neo4j_client import neo4j_client
from app.db.postgres_client import postgres_client
from app.db.redis_client import redis_client
from app.schemas import sim_schemas
from app.services.agent import agent_graph
from app.services.telemetry import INTERVENTION_REGISTRY, apply_vital_tick

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("main")

# --- WebSocket Connection Manager ---
class ConnectionManager:
    def __init__(self):
        # Maps sim_id -> list of active WebSocket connections
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, sim_id: str, websocket: WebSocket):
        await websocket.accept()
        if sim_id not in self.active_connections:
            self.active_connections[sim_id] = []
        self.active_connections[sim_id].append(websocket)
        logger.info(f"WebSocket client connected to session {sim_id}")

    def disconnect(self, sim_id: str, websocket: WebSocket):
        if sim_id in self.active_connections:
            self.active_connections[sim_id].remove(websocket)
            if not self.active_connections[sim_id]:
                del self.active_connections[sim_id]
        logger.info(f"WebSocket client disconnected from session {sim_id}")

    async def broadcast(self, sim_id: str, message: dict):
        if sim_id in self.active_connections:
            websockets = self.active_connections[sim_id]
            tasks = [ws.send_json(message) for ws in websockets]
            await asyncio.gather(*tasks, return_exceptions=True)

manager = ConnectionManager()

# --- Asynchronous Ticker Loop ---
async def vitals_ticker_loop():
    """
    Ticks at 1Hz, fetching all active simulations in Redis, deteriorating vitals,
    checking death status, and broadcasting telemetry.
    """
    logger.info("Starting background vitals ticker loop.")
    while True:
        try:
            active_sims = await redis_client.get_active_simulations()
            for sim_id in active_sims:
                # 1. Fetch state
                state = await redis_client.get_simulation_state(sim_id)
                if not state or state.get("status") != "running":
                    continue

                # 2. Advance clock and apply deterioration formulas
                updated_state = apply_vital_tick(state)

                # 3. Check for critical collapse / death
                if updated_state["vitals_spo2"] <= 45.0 or updated_state["vitals_bps"] <= 40.0:
                    updated_state["status"] = "failed"
                    await postgres_client.update_simulation_state(
                        sim_id=sim_id,
                        status="failed",
                        total_cost=updated_state["total_spent"],
                        elapsed_seconds=updated_state["elapsed_seconds"]
                    )
                    await manager.broadcast(sim_id, {
                        "type": "simulation_ended",
                        "status": "failed",
                        "reason": "Patient coded. Cardiorespiratory arrest occurred."
                    })
                    await redis_client.remove_simulation(sim_id)
                    logger.warning(f"Simulation {sim_id} terminated: patient died.")
                    continue

                # 4. Save updated state back to Redis
                await redis_client.update_simulation_state(sim_id, updated_state)

                # 5. Broadcast telemetry updates
                vitals_packet = {
                    "type": "vitals_update",
                    "sim_id": sim_id,
                    "case_id": updated_state["case_id"],
                    "status": updated_state["status"],
                    "elapsed_seconds": updated_state["elapsed_seconds"],
                    "simulated_minutes": updated_state["simulated_minutes"],
                    "vitals_hr": updated_state["vitals_hr"],
                    "vitals_bps": updated_state["vitals_bps"],
                    "vitals_bpd": updated_state["vitals_bpd"],
                    "vitals_spo2": updated_state["vitals_spo2"],
                    "vitals_temp": updated_state["vitals_temp"],
                    "anxiety": updated_state["anxiety"],
                    "stabilized": updated_state["stabilized"],
                    "budget_remaining": max(0.0, updated_state["budget"] - updated_state["total_spent"])
                }
                await manager.broadcast(sim_id, vitals_packet)
        except Exception as e:
            logger.error(f"Error in vitals ticker loop: {e}", exc_info=True)
        
        await asyncio.sleep(1.0)

# --- Lifespan Manager ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions — non-fatal: app starts even if a DB is temporarily unavailable
    try:
        await neo4j_client.connect()
    except Exception as e:
        logger.warning(f"Neo4j unavailable at startup (sim/chat endpoints will fail): {e}")

    try:
        await postgres_client.connect()
    except Exception as e:
        logger.warning(f"PostgreSQL unavailable at startup (logging will fail): {e}")

    try:
        await redis_client.connect()
    except Exception as e:
        logger.warning(f"Redis unavailable at startup (simulation state will fail): {e}")

    # Start the background ticker
    ticker_task = asyncio.create_task(vitals_ticker_loop())

    yield

    # Shutdown actions
    ticker_task.cancel()
    try:
        await ticker_task
    except asyncio.CancelledError:
        pass

    await redis_client.close()
    await postgres_client.close()
    try:
        await neo4j_client.close()
    except Exception:
        pass



# --- App Definition ---
app = FastAPI(
    title="PulseSim API",
    version="1.0",
    description="Medical Student AI Patient Simulator Backend Service",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- REST Endpoints ---

@app.post("/api/simulation/start", response_model=Dict[str, Any])
async def start_simulation(payload: sim_schemas.SimulationStart):
    """
    Initializes a new simulation. Verifies clinical case existence in Neo4j,
    logs metadata in Postgres, and caches state variables in Redis.
    """
    # 1. Fetch case from Neo4j
    case_data = await neo4j_client.fetch_case_by_id(payload.case_id)
    if not case_data:
        raise HTTPException(status_code=404, detail=f"Clinical case {payload.case_id} not found in graph database.")

    # 2. Record simulation session in Postgres
    sim_id = await postgres_client.create_simulation(
        user_email=payload.user_email,
        case_id=payload.case_id
    )

    # 3. Cache baseline variables in Redis
    await redis_client.initialize_simulation(
        sim_id=sim_id,
        case_id=payload.case_id,
        case_data=case_data
    )

    # 4. Write system initiation log
    await postgres_client.add_chat_log(
        sim_id=sim_id,
        speaker="system",
        transcript=f"Simulation session created for {payload.user_email}."
    )

    return {
        "simulation_id": sim_id,
        "case": {
            "title": case_data["case"]["title"],
            "difficulty": case_data["case"]["difficulty"],
            "patient_age": case_data["case"]["patient_age"],
            "patient_gender": case_data["case"]["patient_gender"],
            "symptoms": [s["name"] for s in case_data["symptoms"]]
        }
    }

@app.post("/api/simulation/{sim_id}/intervention", response_model=sim_schemas.InterventionResponse)
async def execute_intervention(sim_id: str, payload: sim_schemas.InterventionRequest):
    """
    Administers a clinical medication, laboratory assay, or imaging request.
    Applies the effect to telemetry state immediately (<200ms latency requirement).
    """
    # 1. Check if simulation is active
    state = await redis_client.get_simulation_state(sim_id)
    if not state or state.get("status") != "running":
        raise HTTPException(status_code=400, detail="Simulation session is not currently running.")

    # 2. Fetch intervention from registry
    intervention_id = payload.intervention_id
    if intervention_id not in INTERVENTION_REGISTRY:
        raise HTTPException(status_code=400, detail=f"Intervention {intervention_id} is not supported.")
    
    registry_entry = INTERVENTION_REGISTRY[intervention_id]
    cost = registry_entry["cost"]
    time_penalty = registry_entry["time_penalty_minutes"]
    effects = registry_entry["effects"]
    display_name = registry_entry["display_name"]
    duration = registry_entry.get("effect_duration", 0)

    # 3. Check virtual budget
    if state["total_spent"] + cost > state["budget"]:
        raise HTTPException(status_code=400, detail="Financial budget limit exceeded.")

    # 4. Mutate State & Apply Stabilization Trajectory
    state["total_spent"] += cost
    state["simulated_minutes"] += time_penalty

    # If it is a drug/stabilizing agent, add to active treatments
    if effects:
        tx_item = {
            "name": intervention_id,
            "start_elapsed": state["elapsed_seconds"],
            "duration": duration,
            "effects": effects
        }
        state["active_treatments"].append(tx_item)

    # 5. Apply an immediate tick so that the vitals shift reflects instantly (<200ms)
    updated_state = apply_vital_tick(state)
    await redis_client.update_simulation_state(sim_id, updated_state)

    # 6. Save intervention audit log in Postgres
    await postgres_client.add_intervention(
        sim_id=sim_id,
        action_taken=display_name,
        cost_incurred=cost,
        simulated_minute_offset=updated_state["simulated_minutes"]
    )

    # 7. Broadcast instant vital state update packet
    vitals_packet = {
        "type": "vitals_update",
        "sim_id": sim_id,
        "case_id": updated_state["case_id"],
        "status": updated_state["status"],
        "elapsed_seconds": updated_state["elapsed_seconds"],
        "simulated_minutes": updated_state["simulated_minutes"],
        "vitals_hr": updated_state["vitals_hr"],
        "vitals_bps": updated_state["vitals_bps"],
        "vitals_bpd": updated_state["vitals_bpd"],
        "vitals_spo2": updated_state["vitals_spo2"],
        "vitals_temp": updated_state["vitals_temp"],
        "anxiety": updated_state["anxiety"],
        "stabilized": updated_state["stabilized"],
        "budget_remaining": max(0.0, updated_state["budget"] - updated_state["total_spent"])
    }
    await manager.broadcast(sim_id, vitals_packet)

    return sim_schemas.InterventionResponse(
        success=True,
        display_name=display_name,
        cost=cost,
        time_penalty_minutes=time_penalty,
        new_simulated_minutes=updated_state["simulated_minutes"],
        message=f"{display_name} successfully executed."
    )

@app.get("/api/simulation/{sim_id}/state", response_model=sim_schemas.VitalsState)
async def get_state(sim_id: str):
    """
    Fetches the live cache variables. Used for state recovery if the client crashes.
    """
    state = await redis_client.get_simulation_state(sim_id)
    if not state:
        raise HTTPException(status_code=404, detail="Active simulation session not found.")
    
    return sim_schemas.VitalsState(
        sim_id=sim_id,
        case_id=state["case_id"],
        status=state["status"],
        elapsed_seconds=state["elapsed_seconds"],
        simulated_minutes=state["simulated_minutes"],
        vitals_hr=state["vitals_hr"],
        vitals_bps=state["vitals_bps"],
        vitals_bpd=state["vitals_bpd"],
        vitals_spo2=state["vitals_spo2"],
        vitals_temp=state["vitals_temp"],
        anxiety=state["anxiety"],
        stabilized=state["stabilized"],
        budget_remaining=max(0.0, state["budget"] - state["total_spent"])
    )


@app.post("/api/simulation/{sim_id}/chat", response_model=Dict[str, Any])
async def chat_with_patient(sim_id: str, payload: sim_schemas.ChatMessage):
    """
    Routes dialogue through LangGraph. Integrates the zero-hallucination graph context 
    and handles chat-based intervention routing.
    """
    # 1. Verify simulation is active
    state_vitals = await redis_client.get_simulation_state(sim_id)
    if not state_vitals or state_vitals.get("status") != "running":
        raise HTTPException(status_code=400, detail="Simulation session is not currently running.")
        
    # 2. Invoke LangGraph Orchestrator
    input_state = {
        "sim_id": sim_id,
        "user_input": payload.message,
        "input_type": "inquiry",
        "case_id": state_vitals["case_id"],
        "vitals": state_vitals,
        "neo4j_context": {},
        "patient_response": "",
        "grading_result": {}
    }
    
    try:
        output_state = await agent_graph.ainvoke(input_state)
    except Exception as e:
        logger.error(f"LangGraph execution failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to invoke LangGraph orchestrator.")

    patient_reply = output_state.get("patient_response", "")
    input_type = output_state.get("input_type", "inquiry")

    # 3. Log chat history in PostgreSQL
    await postgres_client.add_chat_log(sim_id, "student", payload.message)
    await postgres_client.add_chat_log(sim_id, "patient", patient_reply)

    # 4. If the agent detected a verbal intervention, execute it automatically!
    if input_type == "intervention":
        matched_id = None
        for int_id, entry in INTERVENTION_REGISTRY.items():
            if int_id.replace("_", " ") in payload.message.lower() or entry["display_name"].lower() in payload.message.lower():
                matched_id = int_id
                break
        
        if matched_id:
            logger.info(f"Chat routed intervention triggered: {matched_id}")
            registry_entry = INTERVENTION_REGISTRY[matched_id]
            cost = registry_entry["cost"]
            time_penalty = registry_entry["time_penalty_minutes"]
            effects = registry_entry["effects"]
            display_name = registry_entry["display_name"]
            duration = registry_entry.get("effect_duration", 0)

            if state_vitals["total_spent"] + cost <= state_vitals["budget"]:
                state_vitals["total_spent"] += cost
                state_vitals["simulated_minutes"] += time_penalty
                if effects:
                    state_vitals["active_treatments"].append({
                        "name": matched_id,
                        "start_elapsed": state_vitals["elapsed_seconds"],
                        "duration": duration,
                        "effects": effects
                    })
                
                updated_vitals = apply_vital_tick(state_vitals)
                await redis_client.update_simulation_state(sim_id, updated_vitals)
                
                await postgres_client.add_intervention(
                    sim_id=sim_id,
                    action_taken=f"[Spoken] {display_name}",
                    cost_incurred=cost,
                    simulated_minute_offset=updated_vitals["simulated_minutes"]
                )
                
                # Broadcast immediately
                vitals_packet = {
                    "type": "vitals_update",
                    "sim_id": sim_id,
                    "case_id": updated_vitals["case_id"],
                    "status": updated_vitals["status"],
                    "elapsed_seconds": updated_vitals["elapsed_seconds"],
                    "simulated_minutes": updated_vitals["simulated_minutes"],
                    "vitals_hr": updated_vitals["vitals_hr"],
                    "vitals_bps": updated_vitals["vitals_bps"],
                    "vitals_bpd": updated_vitals["vitals_bpd"],
                    "vitals_spo2": updated_vitals["vitals_spo2"],
                    "vitals_temp": updated_vitals["vitals_temp"],
                    "anxiety": updated_vitals["anxiety"],
                    "stabilized": updated_vitals["stabilized"],
                    "budget_remaining": max(0.0, updated_vitals["budget"] - updated_vitals["total_spent"])
                }
                await manager.broadcast(sim_id, vitals_packet)
                
                patient_reply += f"\n\n[System: Student's spoken command triggered {display_name} stabilization effects.]"

    return {
        "reply": patient_reply,
        "distressed": state_vitals.get("anxiety", 0) > 75.0
    }

@app.post("/api/simulation/{sim_id}/submit", response_model=Dict[str, Any])
async def submit_diagnosis(sim_id: str, payload: sim_schemas.ChatMessage):
    """
    Submits student's diagnostic formulation. Terminates simulation, triggers 
    the EvaluationEngine node, logs metrics, and returns the grading sheet.
    """
    # 1. Verify simulation is active
    state_vitals = await redis_client.get_simulation_state(sim_id)
    if not state_vitals:
        raise HTTPException(status_code=404, detail="Active simulation session not found.")
        
    # 2. Invoke LangGraph Orchestrator with 'submission' intent
    input_state = {
        "sim_id": sim_id,
        "user_input": payload.message,
        "input_type": "submission",
        "case_id": state_vitals["case_id"],
        "vitals": state_vitals,
        "neo4j_context": {},
        "patient_response": "",
        "grading_result": {}
    }
    
    try:
        output_state = await agent_graph.ainvoke(input_state)
    except Exception as e:
        logger.error(f"LangGraph evaluation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to run grading evaluation.")
        
    grades = output_state.get("grading_result", {})

    # 3. Update PostgreSQL session record
    await postgres_client.update_simulation_state(
        sim_id=sim_id,
        status="completed",
        total_cost=state_vitals["total_spent"],
        elapsed_seconds=state_vitals["elapsed_seconds"]
    )
    
    # 4. Log final diagnostic submission message
    await postgres_client.add_chat_log(sim_id, "student", f"[Diagnosis Submission] {payload.message}")
    
    # 5. Broadcast termination through WebSockets
    await manager.broadcast(sim_id, {
        "type": "simulation_ended",
        "status": "completed",
        "reason": f"Diagnostic formulation submitted: {payload.message}"
    })

    # 6. Delete transient state from Redis
    await redis_client.remove_simulation(sim_id)

    return grades

from fastapi.staticfiles import StaticFiles

# --- WebSocket Channel Endpoints ---

@app.websocket("/ws/sim/{sim_id}")
async def websocket_telemetry_endpoint(websocket: WebSocket, sim_id: str):
    """
    Accepts WebSocket connection. Receives incoming client communications (e.g. heartbeat)
    and acts as a real-time broadcast terminal for vitals degradation streams.
    """
    await manager.connect(sim_id, websocket)
    try:
        # Keep client connection open to receive messages/heartbeats
        while True:
            data = await websocket.receive_text()
            # Respond to a simple ping/heartbeat from client to keep channel open
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(sim_id, websocket)
    except Exception as e:
        logger.error(f"WebSocket session {sim_id} encountered an error: {e}")
        manager.disconnect(sim_id, websocket)

# --- Mount Static Frontend Client ---
import os
_frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend")
try:
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")
    logger.info(f"Mounted static frontend files from: {_frontend_dir}")
except Exception as e:
    logger.error(f"Failed to mount static frontend files: {e}")

