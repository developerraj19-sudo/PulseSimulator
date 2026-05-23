import logging
import uuid
from typing import Dict, Any, List, Optional
import asyncpg
from app.config import settings

logger = logging.getLogger("postgres_client")

class PostgresClient:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """Initializes the asyncpg connection pool."""
        if not self.pool:
            try:
                dsn = settings.DATABASE_URL
                # asyncpg does not recognize standard postgresql+asyncpg dialacts
                if dsn.startswith("postgresql+asyncpg://"):
                    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")
                self.pool = await asyncpg.create_pool(dsn)
                logger.info("Connected to PostgreSQL database successfully.")
            except Exception as e:
                logger.error(f"Failed to connect to PostgreSQL: {e}")
                raise e

    async def close(self) -> None:
        """Closes the connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("PostgreSQL database connection pool closed.")

    async def execute(self, query: str, *args) -> str:
        """Executes a command (INSERT, UPDATE, DELETE)."""
        if not self.pool:
            raise RuntimeError("PostgresClient is not connected. Call connect() first.")
        async with self.pool.acquire() as conn:
            try:
                return await conn.execute(query, *args)
            except Exception as e:
                logger.error(f"PostgreSQL execute error: {e}\nQuery: {query}\nArgs: {args}")
                raise e

    async def fetch(self, query: str, *args) -> List[Dict[str, Any]]:
        """Executes a SELECT query and returns a list of dictionaries."""
        if not self.pool:
            raise RuntimeError("PostgresClient is not connected. Call connect() first.")
        async with self.pool.acquire() as conn:
            try:
                records = await conn.fetch(query, *args)
                return [dict(record) for record in records]
            except Exception as e:
                logger.error(f"PostgreSQL fetch error: {e}\nQuery: {query}\nArgs: {args}")
                raise e

    async def fetchrow(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Executes a SELECT query and returns the first row as a dictionary, or None."""
        if not self.pool:
            raise RuntimeError("PostgresClient is not connected. Call connect() first.")
        async with self.pool.acquire() as conn:
            try:
                record = await conn.fetchrow(query, *args)
                return dict(record) if record else None
            except Exception as e:
                logger.error(f"PostgreSQL fetchrow error: {e}\nQuery: {query}\nArgs: {args}")
                raise e

    # --- High-Level Application Operations ---

    async def create_simulation(self, user_email: str, case_id: str) -> str:
        """
        Creates or updates a user and opens a new simulation session.
        Returns the generated UUID session string.
        """
        user_query = """
        INSERT INTO users (email, role) 
        VALUES ($1, 'student')
        ON CONFLICT (email) DO UPDATE SET email = EXCLUDED.email
        RETURNING id;
        """
        user_rec = await self.fetchrow(user_query, user_email)
        user_id = user_rec["id"]

        sim_query = """
        INSERT INTO simulations (user_id, case_id, status)
        VALUES ($1, $2, 'running')
        RETURNING id;
        """
        sim_rec = await self.fetchrow(sim_query, user_id, case_id)
        return str(sim_rec["id"])

    async def add_chat_log(self, sim_id: str, speaker: str, transcript: str, sentiment_score: float = 0.0) -> int:
        """Logs a chat message (student, patient, or system system logs)."""
        query = """
        INSERT INTO chat_logs (sim_id, speaker, transcript, sentiment_score)
        VALUES ($1, $2, $3, $4)
        RETURNING id;
        """
        rec = await self.fetchrow(query, uuid.UUID(sim_id), speaker, transcript, sentiment_score)
        return rec["id"]

    async def add_intervention(self, sim_id: str, action_taken: str, cost_incurred: float, simulated_minute_offset: int) -> int:
        """Registers a diagnostic test, image scan, or drug administration."""
        query = """
        INSERT INTO interventions (sim_id, action_taken, cost_incurred, simulated_minute_offset)
        VALUES ($1, $2, $3, $4)
        RETURNING id;
        """
        rec = await self.fetchrow(query, uuid.UUID(sim_id), action_taken, cost_incurred, simulated_minute_offset)
        return rec["id"]

    async def update_simulation_state(self, sim_id: str, status: str, total_cost: float, elapsed_seconds: int) -> None:
        """Updates the status and cost metrics of the active simulation session."""
        query = """
        UPDATE simulations
        SET status = $2, total_cost = $3, elapsed_seconds = $4
        WHERE id = $1;
        """
        await self.execute(query, uuid.UUID(sim_id), status, total_cost, elapsed_seconds)

    async def get_simulation_summary(self, sim_id: str) -> Dict[str, Any]:
        """
        Aggregates simulation history, chat records, and interventions.
        Useful for running final performance evaluation pipelines.
        """
        sim_id_uuid = uuid.UUID(sim_id)
        
        sim = await self.fetchrow("SELECT * FROM simulations WHERE id = $1;", sim_id_uuid)
        chats = await self.fetch("SELECT speaker, transcript, sentiment_score, timestamp FROM chat_logs WHERE sim_id = $1 ORDER BY timestamp ASC;", sim_id_uuid)
        interventions = await self.fetch("SELECT action_taken, cost_incurred, simulated_minute_offset, execution_time FROM interventions WHERE sim_id = $1 ORDER BY execution_time ASC;", sim_id_uuid)

        # Convert timestamps for JSON compatibility
        if sim:
            sim["created_at"] = sim["created_at"].isoformat()
        for chat in chats:
            chat["timestamp"] = chat["timestamp"].isoformat()
            chat["sentiment_score"] = float(chat["sentiment_score"])
        for inter in interventions:
            inter["execution_time"] = inter["execution_time"].isoformat()
            inter["cost_incurred"] = float(inter["cost_incurred"])

        return {
            "simulation": sim,
            "chat_logs": chats,
            "interventions": interventions
        }

postgres_client = PostgresClient()
