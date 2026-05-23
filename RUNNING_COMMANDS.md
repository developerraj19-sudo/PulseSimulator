# Running PulseSim - Step by Step Commands

This guide provides the exact commands to run the PulseSim application. Choose the method that best fits your environment.

## Option 1: Quick Start with Docker Compose (Recommended)
This method spins up the entire stack, including the backend, frontend, PostgreSQL, Redis, and Neo4j databases automatically.

```bash
# 1. Open your terminal and navigate to the project root
cd d:\PulseSim

# 2. Start all services in the background
docker-compose up -d --build

# 3. To view logs and ensure everything started correctly
docker-compose logs -f

# 4. Access the application
# Open your browser and go to: http://localhost:8000/

# 5. To stop the application later
docker-compose down
```

---

## Option 2: Using the PowerShell Launcher Script (Windows)
If you already have your databases running and want to launch the backend automatically using PowerShell.

```powershell
# 1. Open PowerShell and navigate to the project root
cd d:\PulseSim

# 2. Run the provided bootstrap script
# This script creates a virtual environment, installs packages, and starts the server.
.\run_pulsesim.ps1

# 3. Access the application
# Open your browser and go to: http://localhost:8000/
```

---

## Option 3: Manual Step-by-Step Execution
If you prefer to start the application manually or are doing backend development. (Ensure your databases are running first).

```bash
# 1. Navigate to the backend directory
cd d:\PulseSim\backend

# 2. Create a Python virtual environment
python -m venv venv

# 3. Activate the virtual environment
# On Windows:
.\venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# 4. Install required Python packages
pip install -r requirements.txt

# 5. Set up the environment variables configuration
# (Only needed the first time)
copy .env.example .env

# 6. Run the FastAPI development server
uvicorn app.main:app --reload --port 8000

# 7. Access the application
# Open your browser and go to: http://localhost:8000/
```
