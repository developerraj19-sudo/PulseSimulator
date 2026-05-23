import logging
from typing import Dict, Any, List, Optional
from neo4j import AsyncGraphDatabase
from app.config import settings

logger = logging.getLogger("neo4j_client")

class Neo4jClient:
    def __init__(self):
        self._driver = None

    async def connect(self) -> None:
        """Initializes the Neo4j Async Driver."""
        if not self._driver:
            try:
                self._driver = AsyncGraphDatabase.driver(
                    settings.NEO4J_URI,
                    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
                )
                # Verify connection
                await self._driver.verify_connectivity()
                logger.info("Connected to Neo4j database successfully.")
            except Exception as e:
                logger.error(f"Failed to connect to Neo4j: {e}")
                raise e

    async def close(self) -> None:
        """Closes the Neo4j driver connection."""
        if self._driver:
            await self._driver.close()
            self._driver = None
            logger.info("Neo4j database connection closed.")

    async def execute_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Executes a query and returns a list of records as dictionaries."""
        if not self._driver:
            raise RuntimeError("Neo4j driver is not connected. Call connect() first.")
        
        async with self._driver.session() as session:
            try:
                result = await session.run(query, parameters or {})
                records = await result.data()
                return records
            except Exception as e:
                logger.error(f"Neo4j Query Error: {e}\nQuery: {query}")
                raise e

    async def fetch_case_by_id(self, case_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches the clinical case details, presenting disease, symptoms, and lab profiles.
        """
        query = """
        MATCH (c:ClinicalCase {id: $case_id})-[:PRESENTING_WITH]->(d:Disease)
        OPTIONAL MATCH (d)-[r:EXHIBITS]->(s:Symptom)
        OPTIONAL MATCH (d)-[:HAS_LAB_PROFILE]->(l:LabResult)
        RETURN c AS case, d AS disease,
               collect(DISTINCT {
                   name: s.name, 
                   baseline_severity: s.baseline_severity, 
                   body_part: s.body_part, 
                   probability: r.probability
               }) AS symptoms,
               collect(DISTINCT {
                   test_name: l.test_name, 
                   parameter: l.parameter, 
                   value: l.value, 
                   unit: l.unit
               }) AS labs
        """
        records = await self.execute_query(query, {"case_id": case_id})
        if not records or not records[0].get("case"):
            return None
        return records[0]

    async def check_symptom_exists(self, case_id: str, symptom_name: str) -> Optional[Dict[str, Any]]:
        """
        Validates if a symptom exists for the disease associated with the current case.
        Helps prevent hallucination by verifying clinical reality.
        """
        query = """
        MATCH (c:ClinicalCase {id: $case_id})-[:PRESENTING_WITH]->(d:Disease)-[r:EXHIBITS]->(s:Symptom)
        WHERE toLower(s.name) CONTAINS toLower($symptom_name)
        RETURN s.name AS name, s.baseline_severity AS baseline_severity, s.body_part AS body_part
        LIMIT 1
        """
        records = await self.execute_query(query, {"case_id": case_id, "symptom_name": symptom_name})
        return records[0] if records else None

    async def fetch_lab_result(self, case_id: str, test_name: str, parameter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Queries the database for lab results associated with a case.
        """
        query = """
        MATCH (c:ClinicalCase {id: $case_id})-[:PRESENTING_WITH]->(d:Disease)-[:HAS_LAB_PROFILE]->(l:LabResult)
        WHERE toLower(l.test_name) CONTAINS toLower($test_name)
        AND ($parameter IS NULL OR toLower(l.parameter) CONTAINS toLower($parameter))
        RETURN l.test_name AS test_name, l.parameter AS parameter, l.value AS value, l.unit AS unit
        """
        return await self.execute_query(query, {
            "case_id": case_id,
            "test_name": test_name,
            "parameter": parameter
        })

neo4j_client = Neo4jClient()
