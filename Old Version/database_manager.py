from __future__ import annotations

import logging
from typing import Any, List, Dict

from py2neo import Graph


class DatabaseManager:
    def __init__(self, db_uri: str, db_user: str, db_password: str) -> None:
        try:
            self.graph = Graph(db_uri, auth=(db_user, db_password))
            logging.info("Connected to the database successfully.")
        except Exception as e:
            logging.error(f"Error connecting to the database: {e}")
            raise

    def execute_query(self, query: str, **params: Any) -> List[Dict[str, Any]]:
        logging.info(f"Executing query: {query.strip()}")
        try:
            result = self.graph.run(query, **params).data()
            logging.info(f"Query executed successfully. Result: {result}")
            return result
        except Exception as e:
            logging.error(f"Error executing query '{query}' with params {params}: {e}")
            raise
