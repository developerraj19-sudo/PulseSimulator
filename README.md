# PulseSim: Medical Student AI Patient Simulator

## 🌟 Overview & Professional Summary

**PulseSim** is a state-of-the-art, interactive clinical simulation training engine designed to elevate medical education. By bridging the gap between theoretical knowledge and real-world clinical decision-making, PulseSim immerses students in high-fidelity, high-stakes medical scenarios.

The platform wraps a rigorous **real-time vitals state machine**, dynamic **graph database clinical cases**, and an exhaustive **student intervention logging panel** within a sleek, dark-mode telemetry dashboard. 

### Key Capabilities:
- **Dynamic Patient Simulation**: Simulates physiological responses to both disease progression and medical interventions in real-time.
- **Evidence-Based Case Management**: Powered by Neo4j graph databases to ensure clinical accuracy and contextual symptom probabilities.
- **Comprehensive Audit Trails**: Logs every student action, providing instructors with detailed transcripts for debriefing and assessment.
- **Low-Latency Telemetry**: Uses WebSockets and Redis caching to ensure the dashboard reflects patient status instantly, mimicking real intensive care unit (ICU) monitors.

---

## 🛠️ Tech Stack & Dependencies

- **Frontend**: HTML5, Vanilla CSS3 (Glassmorphism), Vanilla ES6 JavaScript (Native WebSockets, DOM updates).
- **Backend API**: Python (FastAPI, WebSockets, Asyncio task tickers).
- **Databases**: 
  - **Neo4j** (Clinical Case Truth and symptom probabilities).
  - **Redis** (Live session cache, active vitals, and treatment lists).
  - **PostgreSQL** (Student accounts, session transcripts, and intervention audits).

---

## 📂 Project Structure

```
d:/PulseSim/
├── scripts/
│   ├── init_neo4j.cypher         # Neo4j constraints & case data
│   └── init_postgres.sql         # PostgreSQL tables and default users
└── backend/
    ├── requirements.txt          # Python dependencies
    ├── .env.example              # Variables template
    ├── app/
    │   ├── main.py               # FastAPI application & websocket managers
    │   ├── config.py             # Settings configurations
    │   ├── db/
    │   │   ├── neo4j_client.py   # Neo4j query wrappers
    │   │   ├── postgres_client.py# PostgreSQL logging clients
    │   │   └── redis_client.py   # Redis live state handlers
    │   ├── schemas/
    │   │   └── sim_schemas.py    # Request/Response models
    │   └── services/
    │       └── telemetry.py      # Core vital degradation calculations
    └── tests/
        └── test_telemetry.py     # State machine unit tests
```

---

## 🚀 Installation & Running Guide

### 1. Database Initialization

Ensure you have **Neo4j**, **Redis**, and **PostgreSQL** running locally or in Docker.

#### Neo4j Seeding
Execute the Cypher queries in [scripts/init_neo4j.cypher](file:///d:/PulseSim/scripts/init_neo4j.cypher) in your Neo4j browser or via `cypher-shell`.

#### PostgreSQL Setup
Create a database named `pulsesim` and run the SQL table creation script in [scripts/init_postgres.sql](file:///d:/PulseSim/scripts/init_postgres.sql).

---

### 2. Backend Environment Configuration

1. Move to the backend folder:
   ```bash
   cd d:/PulseSim/backend
   ```
2. Copy the configuration file:
   ```bash
   copy .env.example .env
   ```
3. Open `.env` and fill in your connection details (hostnames, ports, credentials, and optional OpenAI API key).

---

### 3. Server Startup

1. Create a Python virtual environment and activate it:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   ```
2. Install Python packages:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   uvicorn app.main:app --reload
   ```

---

### 4. Visualizing the Dashboard

Once the server starts, the frontend is served directly on the root endpoint. 
1. Open your web browser and go to:
   ```
   http://localhost:8000/
   ```
2. Enter a student email (`student@pulsesim.edu`), select a medical case, and click **Start Sim** to begin clinical training.
