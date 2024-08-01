import os
import logging

import shortuuid
import re

from typing import Dict, Any, List
from dotenv import load_dotenv
from py2neo import Graph

# logg only for main.py

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    filename="main.log",
    filemode="w",
)
logger = logging.getLogger(__name__)


class NodeNotFoundError(Exception):
    def __init__(self, node):
        message = f"The node '{node}' was not found in the graph."
        super(NodeNotFoundError, self).__init__(message)


class SameNodeError(Exception):
    def __init__(self):
        message = "The start node and end node cannot be the same in a relationship."
        super(SameNodeError, self).__init__(message)


class NodeIdNotFoundError(Exception):
    def __init__(self, node_name):
        message = f"The node ID for '{node_name}' was not found."
        super(NodeIdNotFoundError, self).__init__(message)


class InsufficientNodesError(Exception):
    def __init__(self):
        message = "Insufficient information to delete a relationship (Provide ID or Start and End Node)."
        super(InsufficientNodesError, self).__init__(message)


class RelationshipNotFoundError(Exception):
    def __init__(self):
        message = "The Relationship was not found in the graph."
        super(RelationshipNotFoundError, self).__init__(message)


class DuplicateNodeNameError(Exception):
    def __init__(self, name):
        message = f"A node with the name '{name}' already exists."
        super(DuplicateNodeNameError, self).__init__(message)


class Node:
    def __init__(
        self,
        name: str,
        primary_label: str,
        properties: Dict[Any, Any] = None,
    ):

        # name and primary_label are required

        self.name = name
        self.labels = [primary_label]
        self.properties = properties or {}
        self.node_id = f"n_{shortuuid.uuid()[:6]}"

    def __eq__(self, other):
        if isinstance(other, Node):
            return self.node_id == other.node_id
        return NotImplemented

    def modify_name(self, new_name: str):

        # Ensure the name is modified only if it is different from the current name

        if new_name != self.name:
            self.name = new_name

    def add_label(self, label: str):

        # Ensure the label is added only if it does not exist

        if label not in self.labels:
            self.labels.append(label)

    def modify_label(self, old_label: str, new_label: str):

        # Ensure the label is modified only if it exists

        if old_label in self.labels:
            self.labels[self.labels.index(old_label)] = new_label

    def delete_label(self, label: str):

        # Ensure the label is deleted only if it exists, and it is not the primary label

        if label in self.labels and label != self.labels[0]:
            self.labels.remove(label)

    def add_property(self, key: Any, value: Any):

        # Ensure the property is added only if it does not exist

        if key not in self.properties:
            self.properties[key] = value

    def modify_property(self, key: Any, value: Any):

        # Ensure the property is modified only if it exists

        if key in self.properties:
            self.properties[key] = value

    def delete_property(self, key: Any):

        # Ensure the property is deleted only if it exists

        if key in self.properties:
            del self.properties[key]


class Relationship:
    def __init__(
        self,
        start_node: str,
        rel_type: str,
        end_node: str,
        properties: Dict[Any, Any] = None,
    ):

        # start_node_identifier, rel_type and end_node_identifier are required

        # ensure the relationship type is in uppercase and blanks are replaced by underscores
        # requirement of neo4j

        rel_type = rel_type.upper().replace(" ", "_")

        # strings for start_node_identifier and end_note have to be in the format "n_{shortuuid.uuid()[:6]}"

        self.start_node = start_node
        self.type = rel_type
        self.end_node = end_node
        self.relationship_id = f"r_{shortuuid.uuid()[:6]}"
        self.properties = properties or {}

    def __str__(self):
        return f"{self.start_node} -> {self.type} -> {self.end_node}    ID: {self.relationship_id}"

    def __eq__(self, other):
        if isinstance(other, Relationship):
            return self.relationship_id == other.relationship_id
        return NotImplemented

    def add_property(self, key: Any, value: Any):

        # Ensure the property is added only if it does not exist

        if key not in self.properties:
            self.properties[key] = value

    def modify_property(self, key: Any, value: Any):

        # Ensure the property is modified only if it exists

        if key in self.properties:
            self.properties[key] = value

    def delete_property(self, key: Any):

        # Ensure the property is deleted only if it exists

        if key in self.properties:
            del self.properties[key]


class WorldbuilderGraph:

    # all operations should return the id of the node or relationship created or modified if successful
    # and raise appropriate exceptions if the operation fails

    def __init__(self, uri: str) -> None:
        self.nodes = {}
        self.relationships = {}
        self.node_id_name_map = {}
        self.database_manager = DatabaseManager(uri)
        self.database_operations = DatabaseOperations(self.database_manager)

    def add_node(
        self, name: str, primary_label: str, properties: Dict[Any, Any] = None
    ) -> str or None:
        try:
            self._check_duplicate_node(name)
            node = self._create_node(name, primary_label, properties)
            self._add_node_to_memory(node)
            self._add_node_to_database(node)
            return node.node_id
        except DuplicateNodeNameError as e:
            logger.error(f"Error: {e}")
            print(f"Error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            print(f"Unexpected error: {e}")
            return None

    def _check_duplicate_node(self, name: str) -> None:
        if name in self.node_id_name_map:
            raise DuplicateNodeNameError(name)

    def _create_node(
        self, name: str, primary_label: str, properties: Dict[Any, Any] = None
    ) -> Node:
        return Node(name, primary_label, properties)

    def _add_node_to_memory(self, node: Node) -> None:
        self.nodes[node.node_id] = node
        self.node_id_name_map[node.name] = node.node_id

    def _add_node_to_database(self, node: Node) -> None:
        self.database_operations.do_add_node(
            node.node_id, node.name, node.labels[0], node.properties
        )

    def delete_node(self, identifier: str) -> str:
        node_name, node_id = self.get_name_and_id(identifier)
        self._log_deletion_start(node_name, node_id)
        self._delete_node_from_memory(node_name, node_id)
        self._delete_node_from_database(node_id)
        self._log_deletion_success(node_name, node_id)
        return identifier

    def _log_deletion_start(self, node_name: str, node_id: str) -> None:
        logging.info(
            f"Starting delete node with name {node_name} and ID {node_id} from Worldbuildergraph"
        )

    def _delete_node_from_memory(self, node_name: str, node_id: str) -> None:
        if node_id in self.nodes:
            del self.nodes[node_id]
            del self.node_id_name_map[node_name]
        else:
            raise NodeNotFoundError(node_name)

    def _delete_node_from_database(self, node_id: str) -> None:
        self.database_operations.do_delete_node(node_id)

    def _log_deletion_success(self, node_name: str, node_id: str) -> None:
        logging.info(
            f"Node with name {node_name} and ID {node_id} deleted from Worldbuildergraph"
        )

    def add_relationship(
        self,
        start_node_identifier: str,
        rel_type: str,
        end_node_identifier: str,
        properties: Dict[Any, Any] = None,
    ) -> str:

        start_node_name, start_node_id = self.get_name_and_id(start_node_identifier)
        end_node_name, end_node_id = self.get_name_and_id(end_node_identifier)

        self._validate_nodes(start_node_id, end_node_id)

        relationship = self._create_relationship(
            start_node_name, rel_type, end_node_name, properties
        )

        self._add_relationship_to_memory(relationship)
        self._add_relationship_to_database(
            start_node_id, rel_type, end_node_id, relationship
        )

        return relationship.relationship_id

    def _validate_nodes(self, start_node_id: str, end_node_id: str) -> None:
        if start_node_id == end_node_id:
            raise SameNodeError()

    def _create_relationship(
        self,
        start_node_name: str,
        rel_type: str,
        end_node_name: str,
        properties: Dict[Any, Any] = None,
    ) -> Relationship:
        return Relationship(start_node_name, rel_type, end_node_name, properties)

    def _add_relationship_to_memory(self, relationship: Relationship) -> None:
        self.relationships[relationship.relationship_id] = relationship
        logging.info(
            f"Added relationship {relationship.type} between {relationship.start_node} and {relationship.end_node}"
        )

    def _add_relationship_to_database(
        self,
        start_node_id: str,
        rel_type: str,
        end_node_id: str,
        relationship: Relationship,
    ) -> None:
        self.database_operations.do_add_relationship(
            start_node_id,
            rel_type,
            end_node_id,
            relationship.relationship_id,
            relationship.properties,
        )

    def delete_relationship(
        self,
        relationship_id: str = None,
        start_node_identifier: str = None,
        end_node_identifier: str = None,
        rel_type: str = None,
    ) -> str or None:

        # Check if sufficient information is provided
        if not (relationship_id or (start_node_identifier and end_node_identifier)):
            raise InsufficientNodesError()

        # Delete by relationship_id if provided
        if relationship_id:
            return self._delete_by_relationship_id(relationship_id)

        # Delete by node identifiers and optional relationship type
        return self._delete_by_nodes(
            start_node_identifier, end_node_identifier, rel_type
        )

    def _delete_by_relationship_id(self, relationship_id: str) -> str:
        if relationship_id in self.relationships:
            del self.relationships[relationship_id]
            self.database_operations.do_delete_relationship(relationship_id)
            return relationship_id
        raise RelationshipNotFoundError()

    def _delete_by_nodes(
        self, start_node_identifier: str, end_node_identifier: str, rel_type: str = None
    ) -> None:
        start_node_name, _ = self.get_name_and_id(start_node_identifier)
        end_node_name, _ = self.get_name_and_id(end_node_identifier)

        # Copy to avoid changing the dictionary while iterating
        temp_relationships = self.relationships.copy()

        deleted_any = False
        for rel_id, rel in temp_relationships.items():
            if self._matches_criteria(rel, start_node_name, end_node_name, rel_type):
                del self.relationships[rel_id]
                self.database_operations.do_delete_relationship(rel_id)
                deleted_any = True

        if not deleted_any:
            raise RelationshipNotFoundError()

    @staticmethod
    def _matches_criteria(
        rel, start_node_name: str, end_node_name: str, rel_type: str = None
    ) -> bool:
        return (
            rel.start_node == start_node_name
            and rel.end_node == end_node_name
            and (rel_type is None or rel.type == rel_type)
        )

    @staticmethod
    def is_valid_node_id(identifier: str) -> bool:
        pattern = r"^n_[A-Za-z0-9_-]{6}$"
        return bool(re.match(pattern, identifier))

    def get_name_and_id(self, identifier):

        if self.is_valid_node_id(identifier):
            logging.info(f"Identifier {identifier} is a node ID")
            return self.get_name_by_node_id(identifier), identifier
        else:
            logging.info(f"Identifier {identifier} is a node name")
            return identifier, self.get_node_id_by_name(identifier)

    def get_name_by_node_id(self, node_id: str) -> str:

        if node_id in self.nodes:
            return self.nodes[node_id].name

        raise NodeIdNotFoundError(node_id)

    def get_node_id_by_name(self, name: str) -> str:

        if name in self.node_id_name_map:
            return self.node_id_name_map[name]

        raise NodeNotFoundError(name)


class DatabaseManager:
    def __init__(self, db_adress: str) -> None:
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        try:
            # Establish connection with the database using URI and credentials
            self.graph = Graph(db_adress, auth=(db_user, db_password))
            logger.info("Successfully connected to the database.")
        except Exception as e:
            logger.error(f"Error connecting to the database: {e}")
            raise


class DatabaseOperations:

    # Database operations translate the operations on the WorldbuilderGraph to the database
    # The WorldbuilderGraph is used to keep track of the nodes and relationships in memory
    # These operations are then translated to the database using the DatabaseManager
    # CRUD operations are only to be called from WorldbuilderGraph methods.
    # Other methods can be called from the main application for information gathering.

    def __init__(self, database_manager: DatabaseManager):
        self.database_manager = database_manager

    def execute_query(self, query: str, **params: Any) -> List[Dict[str, Any]]:
        try:
            result = self.database_manager.graph.run(query, **params).data()
            logger.info(f"Query executed successfully. Result: {result}")
            return result
        except Exception as e:
            logger.error(f"Error executing query '{query}' with params {params}: {e}")
            raise

    def create_constraints(self):
        try:
            # Unique constraint on 'name' property for all nodes
            query_name = "CREATE CONSTRAINT unique_name_constraint IF NOT EXISTS ON (n:Label) ASSERT n.name IS UNIQUE"
            self.execute_query(query_name)
            logger.info("Unique constraint on 'name' created successfully.")

            # Unique constraint on 'node_id' property for all nodes
            query_node_id = (
                "CREATE CONSTRAINT unique_node_id_constraint "
                "IF NOT EXISTS ON (n:Label) ASSERT n.node_id IS UNIQUE"
            )
            self.execute_query(query_node_id)
            logger.info("Unique constraint on 'node_id' created successfully.")
        except Exception as e:
            logger.error(f"Error creating constraints: {e}")
            raise

    @staticmethod
    def dict_to_cypher_properties(properties: dict) -> str:

        # Convert dictionary to cypher properties string
        # Remove leading and trailing whitespaces from keys
        # Raise warning if key contains spaces

        properties_string = ", ".join(
            [f"`{k.strip()}`: $`{k.strip()}`" for k in properties.keys()]
        )

        if any(" " in key for key in properties.keys()):
            logger.info(
                "Property keys should not contain spaces. Try to use underscores instead."
            )

        logging.info(f"Properties string: {properties_string}")
        return properties_string

    # CRUD operations for nodes and relationships:

    def erase_all(self) -> None:

        # Erase all nodes and relationships from the database
        try:
            query = "MATCH (n) DETACH DELETE n RETURN count(n) as deleted_nodes"
            logging.info("Erasing all nodes and relationships from the database.")
            self.execute_query(query)

        except Exception as e:
            logging.error(f"Error erasing all nodes and relationships: {e}")
            raise

    def do_add_node(
        self,
        node_id: str,
        name: str,
        primary_label: str,
        properties: Dict[Any, Any] = None,
    ) -> str:

        # generate properties string and include identifier in the properties dictionary
        properties["node_id"] = node_id
        props = self.dict_to_cypher_properties(properties)

        query = f"CREATE (n:{primary_label} {{name: $name, {props}}}) RETURN id(n) as cypher_id"

        try:
            self.execute_query(query, name=name, **properties)
            logger.info(
                f"Node '{name}' with ID {node_id} added successfully to database"
            )
            return node_id
        except Exception as e:
            if "already exists" in str(e):
                raise DuplicateNodeNameError(name)
            logger.error(f"Error adding node to database '{name}': {e}")
            raise

    def do_delete_node(self, node_id: str) -> str:

        query = "MATCH (n {node_id: $node_id}) DETACH DELETE n RETURN count(n) as deleted_nodes"

        try:
            self.execute_query(query, node_id=node_id)
            logger.info(f"Node with ID {node_id} deleted from database successfully")
            return node_id

        except Exception as e:
            logger.error(f"Error deleting node from database with ID {node_id}: {e}")
            raise

    def do_add_relationship(
        self,
        start_node_id: str,
        rel_type: str,
        end_node_id: str,
        relationship_id: str,
        properties: Dict[Any, Any] = None,
    ) -> str:
        # Add relationship between nodes in the database

        properties = {} if properties is None else properties
        properties["relationship_id"] = relationship_id
        properties_string = self.dict_to_cypher_properties(properties)

        query = (
            f"MATCH (start_node {{node_id: $start_node_id}}), (end_node {{node_id: $end_node_id}}) "
            f"CREATE (start_node)-[r:{rel_type} {{{properties_string}}}]->(end_node) "
            "RETURN id(r) as cypher_id"
        )

        try:
            self.execute_query(
                query,
                start_node_id=start_node_id,
                end_node_id=end_node_id,
                **properties,
            )
            logger.info(
                f"Relationship of type '{rel_type}' between nodes "
                f"with IDs {start_node_id} and {end_node_id} added successfully to database"
            )
            return start_node_id

        except Exception as e:
            logger.error(
                f"Error adding relationship to database between nodes with IDs {start_node_id} and {end_node_id}: {e}"
            )
            raise

    def do_delete_relationship(self, relationship_id: str) -> str:

        # Delete relationship from the database

        query = (
            "MATCH ()-[r {relationship_id: $relationship_id}]-() "
            "DELETE r RETURN count(r) as deleted_relationships"
        )

        try:
            self.execute_query(query, relationship_id=relationship_id)
            logger.info(
                f"Relationship with ID {relationship_id} deleted from database successfully"
            )
            return relationship_id

        except Exception as e:
            logger.error(
                f"Error deleting relationship from database with ID {relationship_id}: {e}"
            )
            raise


# Usage
load_dotenv()
db_uri: str | None = os.getenv("DB_URI")

# Create a complex Node with many properties and secondary labels with WorldbuilderGraph fantasy themed

graph = WorldbuilderGraph(db_uri)
graph.database_operations.erase_all()
graph.add_node("Gandalf", "Wizard", {"staff": "Yes", "magic": "Yes", "age": 2019})
graph.add_node("Elminster", "Wizard", {"staff": "Yes", "magic": "Yes", "age": 2000})
print("---")
graph.add_relationship("Gandalf", "FRIEND", "Elminster")
graph.add_relationship("Gandalf", "MENTOR", "Elminster")
graph.add_relationship("Gandalf", "STUDENT", "Elminster")
print("---")
graph.delete_relationship(
    start_node_identifier="Gandalf", end_node_identifier="Elminster"
)
