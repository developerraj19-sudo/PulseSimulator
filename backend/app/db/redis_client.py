import json
import logging
from typing import Dict, Any, List, Optional
import redis.asyncio as aioredis
from app.config import settings

logger = logging.getLogger("redis_client")

class RedisClient:
    def __init__(self):
        self.client: Optional[aioredis.Redis] = None

    async def connect(self) -> None:
        """Initializes the Redis connection."""
        if not self.client:
            try:
                self.client = aioredis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    db=settings.REDIS_DB,
                    decode_responses=True
                )
                # Verify connection
                await self.client.ping()
                logger.info("Connected to Redis successfully.")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise e

    async def close(self) -> None:
        """Closes the Redis client connection."""
        if self.client:
            await self.client.close()
            self.client = None
            logger.info("Redis connection closed.")

    def _get_key(self, sim_id: str) -> str:
        return f"sim:{sim_id}:state"

    async def initialize_simulation(self, sim_id: str, case_id: str, case_data: Dict[str, Any]) -> None:
        """
        Creates a structured hash containing the active simulation details and vitals.
        Seeds baseline parameters directly from the Neo4j node metadata.
        """
        key = self._get_key(sim_id)
        case_info = case_data.get("case", {})

        state = {
            "case_id": case_id,
            "status": "running",
            "elapsed_seconds": "0",
            "simulated_minutes": "0",
            "vitals_hr": str(case_info.get("baseline_hr", 80.0)),
            "vitals_bps": str(case_info.get("baseline_bps", 120.0)),
            "vitals_bpd": str(case_info.get("baseline_bpd", 80.0)),
            "vitals_spo2": str(case_info.get("baseline_spo2", 98.0)),
            "vitals_temp": str(case_info.get("baseline_temp", 37.0)),
            "anxiety": str(case_info.get("anxiety", 50.0)),
            "stabilized": "false",
            "active_treatments": json.dumps([]),
            "budget": "1000.00",
            "total_spent": "0.00"
        }

        # Save to Redis (hmset used for Redis 3.x Windows compatibility)
        await self.client.hmset(key, state)
        # Register as an active running simulation tracking set
        await self.client.sadd("active_simulations", sim_id)
        logger.info(f"Simulation session {sim_id} initialized in Redis.")

    async def get_simulation_state(self, sim_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the deserialized live state from the Redis hash cache.
        """
        if not self.client:
            raise RuntimeError("Redis client is not connected.")
        
        key = self._get_key(sim_id)
        state = await self.client.hgetall(key)
        if not state:
            return None

        # Format types safely
        return {
            "case_id": state.get("case_id"),
            "status": state.get("status"),
            "elapsed_seconds": int(state.get("elapsed_seconds", 0)),
            "simulated_minutes": int(state.get("simulated_minutes", 0)),
            "vitals_hr": float(state.get("vitals_hr", 80.0)),
            "vitals_bps": float(state.get("vitals_bps", 120.0)),
            "vitals_bpd": float(state.get("vitals_bpd", 80.0)),
            "vitals_spo2": float(state.get("vitals_spo2", 98.0)),
            "vitals_temp": float(state.get("vitals_temp", 37.0)),
            "anxiety": float(state.get("anxiety", 50.0)),
            "stabilized": state.get("stabilized") == "true",
            "active_treatments": json.loads(state.get("active_treatments", "[]")),
            "budget": float(state.get("budget", 1000.00)),
            "total_spent": float(state.get("total_spent", 0.00))
        }

    async def update_simulation_state(self, sim_id: str, updates: Dict[str, Any]) -> None:
        """
        Updates fields inside the simulation's state hash.
        Handles serialization of boolean and complex list types.
        """
        if not self.client:
            raise RuntimeError("Redis client is not connected.")
        
        key = self._get_key(sim_id)
        mapping = {}
        for k, v in updates.items():
            if isinstance(v, bool):
                mapping[k] = "true" if v else "false"
            elif isinstance(v, (list, dict)):
                mapping[k] = json.dumps(v)
            else:
                mapping[k] = str(v)

        if mapping:
            await self.client.hmset(key, mapping)

    async def remove_simulation(self, sim_id: str) -> None:
        """Cleans up the cache when a session terminates."""
        if not self.client:
            raise RuntimeError("Redis client is not connected.")
        
        key = self._get_key(sim_id)
        await self.client.delete(key)
        await self.client.srem("active_simulations", sim_id)
        logger.info(f"Simulation session {sim_id} removed from Redis cache.")

    async def get_active_simulations(self) -> List[str]:
        """Returns all simulation IDs currently running in background ticks."""
        if not self.client:
            raise RuntimeError("Redis client is not connected.")
        return await self.client.smembers("active_simulations")

redis_client = RedisClient()
