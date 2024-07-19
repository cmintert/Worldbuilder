from __future__ import annotations

import logging
from typing import Optional, Dict, Any, List, Tuple

from data_classes import Entity, Relationship
from database_manager import DatabaseManager


class GraphDatabaseOperations:
    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db_manager = db_manager

    # Graph Operations

    def sanitize_rel_type(self, rel_type: str) -> str:
        return rel_type.replace(" ", "_").upper()

    def clear_graph(self) -> None:
        query = "MATCH (n) DETACH DELETE n"
        try:
            self.db_manager.execute_query(query)
            logging.info("Graph cleared successfully.")
        except Exception as e:
            logging.error(f"Error clearing the graph: {e}")
            raise

    # Entity Operations

    def create_entity(self, entity: Entity) -> Optional[Dict[str, Any]]:
        query = """
        CREATE (n:Entity $properties)
        RETURN n
        """
        try:
            logging.info(
                f"Attempting to create entity with properties: {entity.get_all_properties()}"
            )
            result = self.db_manager.execute_query(
                query, properties=entity.get_all_properties()
            )
            if result:
                logging.info(f"Entity created successfully: {result[0]['n']}")
                return result[0]["n"]
            else:
                logging.error("Entity creation failed: No result returned.")
                return None
        except Exception as e:
            logging.error(f"Error during entity creation: {e}")
            raise

    def bulk_create_entities(self, entities: List[Entity]) -> None:

        query = """
        UNWIND $entities AS entity
        MERGE (n:Entity {name: entity.name})
        SET n += entity
        """

        print(f"Starting bulk creation of {len(entities)} entities.")
        logging.info(f"Starting bulk creation of {len(entities)} entities.")

        try:
            self.db_manager.execute_query(
                query, entities=[entity.get_all_properties() for entity in entities]
            )
            logging.info("Bulk entity creation/update completed successfully.")
        except Exception as e:
            logging.error(f"Error during bulk entity creation/update: {e}")
            raise

    def read_entity(self, name: str) -> Dict[str, Any]:
        query = """
        MATCH (n:Entity {name: $name})
        RETURN n
        """
        result = self.db_manager.execute_query(query, name=name)
        return result[0]["n"] if result else None

    def update_entity(
        self, name: str, updated_properties: Dict[str, Any]
    ) -> Dict[str, Any]:

        query = """
        MATCH (n:Entity {name: $name})
        SET n += $properties
        RETURN n
        """

        # Fetch existing properties to avoid overwriting
        existing_entity = self.read_entity(name)
        if not existing_entity:
            logging.error(f"Entity {name} not found for update.")
            return None

        logging.info(f"Existing properties: {existing_entity}")
        logging.info(f"Updated properties: {updated_properties}")

        # Merge existing properties with updated ones
        merged_properties = {**existing_entity, **updated_properties}

        logging.info(f"Merged properties: {merged_properties}")

        logging.info(
            f"Executing query: {query.strip()} with name={name} and properties={merged_properties}"
        )

        result = self.db_manager.execute_query(
            query, name=name, properties=merged_properties
        )

        if result:
            logging.info(f"Query result: {result[0]['n']}")
        else:
            logging.error("Query failed to return a result.")

        logging.info(
            f"Exiting update_entity with result: {result[0]['n'] if result else None}"
        )
        return result[0]["n"] if result else None

    def delete_entity(self, name: str) -> None:
        query = """
        MATCH (n:Entity {name: $name})
        DETACH DELETE n
        """
        self.db_manager.execute_query(query, name=name)

    # Relationship Operations

    def create_relationship(
        self,
        source_name: str,
        rel_type: str,
        target_name: str,
        properties: Dict[str, Any] = None,
    ) -> Dict[str, Any]:

        sanitized_type = self.sanitize_rel_type(rel_type)

        query = f"""
        MATCH (a:Entity {{name: $source_name}}), (b:Entity {{name: $target_name}})
        CREATE (a)-[r:{sanitized_type}]->(b)
        SET r.original_type = "{rel_type}"
        RETURN r
        """
        properties = properties or {}
        result = self.db_manager.execute_query(
            query,
            source_name=source_name,
            target_name=target_name,
            properties=properties,
        )
        return result[0]["r"] if result else None

    def bulk_create_relationships(self, relationships: List[Relationship]) -> None:
        logging.info(f"Starting bulk creation of {len(relationships)} relationships.")

        # Group relationships by sanitized type
        rel_groups = {}
        for rel in relationships:
            sanitized_type = self.sanitize_rel_type(rel["type"])
            rel_groups.setdefault(sanitized_type, []).append(rel)

        total_count = 0
        for sanitized_type, rels in rel_groups.items():
            query = f"""
            UNWIND $rels AS rel
            MATCH (a:Entity {{name: rel.source}})
            MATCH (b:Entity {{name: rel.target}})
            MERGE (a)-[r:{sanitized_type}]->(b)
            SET r.original_type = rel.type
            RETURN count(*) as count
            """
            try:
                result = self.db_manager.execute_query(query, rels=rels)
                count = result[0]["count"]
                total_count += count
                logging.info(f"Created {count} relationships of type {sanitized_type}")
            except Exception as e:
                logging.error(
                    f"Error creating relationships of type {sanitized_type}: {e}"
                )
                raise

        logging.info(
            f"Bulk relationship creation completed successfully. Created {total_count} relationships."
        )

    def read_relationships(
        self, entity_name: str, rel_type: str = None
    ) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
        query = """
        MATCH (n:Entity {name: $name})-[r]->(m:Entity)
        WHERE $rel_type IS NULL OR type(r) = $rel_type
        RETURN r, m
        """
        result = self.db_manager.execute_query(
            query, name=entity_name, rel_type=rel_type
        )
        return [(r["r"], r["m"]) for r in result]

    def delete_relationship(
        self, source_name: str, rel_type: str, target_name: str
    ) -> None:
        query = """
        MATCH (a:Entity {name: $source_name})-[r:$rel_type]->(b:Entity {name: $target_name})
        DELETE r
        """
        self.db_manager.execute_query(
            query, source_name=source_name, rel_type=rel_type, target_name=target_name
        )

    # Query Operations

    def query_entities(
        self, entity_type: str = None, name: str = None, description: str = None
    ) -> List[Dict[str, Any]]:

        query = """
        MATCH (n:Entity)
        WHERE ($entity_type IS NULL OR n.entity_type = $entity_type)
          AND ($name IS NULL OR toLower(n.name) CONTAINS toLower($name))
          AND ($description IS NULL OR toLower(n.description) CONTAINS toLower($description))
        RETURN n
        """

        logging.info(
            "Querying entities with filters: "
            f"entity_type={entity_type}, name={name}, description={description}"
        )

        result = self.db_manager.execute_query(
            query, entity_type=entity_type, name=name, description=description
        )

        logging.info(f"Entities found: {result}")

        return [r["n"] for r in result]

    def query_relationships(
        self, source_type: str = None, rel_type: str = None, target_type: str = None
    ) -> List[Dict[str, str]]:

        query = """
        MATCH (a:Entity)-[r]->(b:Entity)
        WHERE ($source_type IS NULL OR a.entity_type = $source_type)
          AND ($rel_type IS NULL OR type(r) = $rel_type)
          AND ($target_type IS NULL OR b.entity_type = $target_type)
        RETURN a.name as source, type(r) as relationship, b.name as target
        """
        result = self.db_manager.execute_query(
            query, source_type=source_type, rel_type=rel_type, target_type=target_type
        )
        return result

    def get_entity_properties(self, entity_name: str) -> Dict[str, Any]:
        query = """
        MATCH (n:Entity {name: $name})
        RETURN properties(n) as props
        """
        result = self.db_manager.execute_query(query, name=entity_name)
        return result[0]["props"] if result else {}
