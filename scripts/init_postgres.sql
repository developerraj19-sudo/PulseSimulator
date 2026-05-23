-- ============================================================================
-- PulseSim: PostgreSQL Schema Initialization
-- Phase 2: Database Schema Definition
-- ============================================================================

-- Enable UUID extension if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Users Table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    role VARCHAR(50) NOT NULL DEFAULT 'student',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Simulations Table
CREATE TABLE IF NOT EXISTS simulations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    case_id VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'running', -- running, paused, completed, failed
    total_cost NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    elapsed_seconds INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Chat Logs Table
CREATE TABLE IF NOT EXISTS chat_logs (
    id SERIAL PRIMARY KEY,
    sim_id UUID NOT NULL REFERENCES simulations(id) ON DELETE CASCADE,
    speaker VARCHAR(50) NOT NULL, -- student, patient, system
    transcript TEXT NOT NULL,
    sentiment_score NUMERIC(4, 3) DEFAULT 0.000, -- From LLM evaluator or API
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Interventions Table
CREATE TABLE IF NOT EXISTS interventions (
    id SERIAL PRIMARY KEY,
    sim_id UUID NOT NULL REFERENCES simulations(id) ON DELETE CASCADE,
    action_taken VARCHAR(255) NOT NULL,
    execution_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, -- Real-world time executed
    simulated_minute_offset INT NOT NULL DEFAULT 0, -- The simulated time offset in minutes
    cost_incurred NUMERIC(10, 2) NOT NULL DEFAULT 0.00
);

-- 5. Indexes for query optimization
CREATE INDEX IF NOT EXISTS idx_simulations_user_id ON simulations(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_logs_sim_id ON chat_logs(sim_id);
CREATE INDEX IF NOT EXISTS idx_interventions_sim_id ON interventions(sim_id);

-- 6. Insert Default admin/student users for testing
INSERT INTO users (email, role) 
VALUES ('student@pulsesim.edu', 'student')
ON CONFLICT (email) DO NOTHING;

INSERT INTO users (email, role) 
VALUES ('educator@pulsesim.edu', 'educator')
ON CONFLICT (email) DO NOTHING;
