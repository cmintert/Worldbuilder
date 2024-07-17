from __future__ import annotations

import os
import logging
import shlex
import json


from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.output.win32 import NoConsoleScreenBufferError
from prompt_toolkit.shortcuts import prompt
from prompt_toolkit.formatted_text import HTML

from py2neo import Graph
from dotenv import load_dotenv
from typing import Callable, Dict, List, Tuple, Any, Optional


class DatabaseManager:
    def __init__(self, db_uri: str, db_user: str, db_password: str) -> None:
        try:
            self.graph = Graph(db_uri, auth=(db_user, db_password))
            logging.info("Connected to the database successfully.")
        except Exception as e:
            logging.error(f"Error connecting to the database: {e}")
            raise

    def execute_query(
        self, query: str, **params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        logging.info(f"Executing query: {query.strip()}")
        try:
            result = self.graph.run(query, **params).data()
            logging.info(f"Query executed successfully. Result: {result}")
            return result
        except Exception as e:
            logging.error(f"Error executing query '{query}' with params {params}: {e}")
            raise


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

    def create_entity(self, entity: "Entity") -> Optional[Dict[str, Any]]:
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

    def bulk_create_entities(self, entities: List["Entity"]) -> None:

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

    def bulk_create_relationships(self, relationships: List[Dict[str, Any]]) -> None:
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


class Entity:
    def __init__(
        self, name: str, entity_type: str, description: str = None, **properties: Any
    ) -> None:
        self._properties = {
            "name": name,
            "entity_type": entity_type,
            "description": description,
        }
        self._properties.update(properties)
        self.relationships = []

    def __getattr__(self, name: str) -> Any:
        return self._properties.get(name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in ["_properties", "relationships"]:
            super().__setattr__(name, value)
        else:
            self._properties[name] = value

    def get_property(self, name: str) -> Any:
        return self._properties.get(name)

    def set_property(self, name: str, value: Any) -> None:
        self._properties[name] = value

    def delete_property(self, name: str) -> None:
        if name not in ["name", "entity_type", "description"]:
            self._properties.pop(name, None)

    def get_all_properties(self) -> Dict[str, Any]:
        return self._properties.copy()

    def add_relationship(
        self, rel_type: str, target: "Entity", **properties: Any
    ) -> "Relationship":
        relationship = Relationship(self, rel_type, target, **properties)
        self.relationships.append(relationship)
        return relationship

    def __repr__(self) -> str:
        return f"Entity(name={self.name}, type={self.entity_type})"


class Relationship:
    def __init__(
        self, source: Entity, rel_type: str, target: Entity, **properties: Any
    ) -> None:
        self._properties = {"source": source, "rel_type": rel_type, "target": target}
        self._properties.update(properties)

    def __getattr__(self, name: str) -> Any:
        return self._properties.get(name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_properties":
            super().__setattr__(name, value)
        else:
            self._properties[name] = value

    def get_property(self, name: str) -> Any:
        return self._properties.get(name)

    def set_property(self, name: str, value: Any) -> None:
        self._properties[name] = value

    def delete_property(self, name: str) -> None:
        if name not in ["source", "rel_type", "target"]:
            self._properties.pop(name, None)

    def get_all_properties(self) -> Dict[str, Any]:
        return self._properties.copy()

    def __repr__(self) -> str:
        return f"{self.source.name} -> {self.rel_type} -> {self.target.name}"


class World:
    def __init__(self, db_uri: str, db_user: str, db_password: str) -> None:
        self.db_manager = DatabaseManager(db_uri, db_user, db_password)
        self.db_operations = GraphDatabaseOperations(self.db_manager)
        self.entities = {}

    def load_data(self, file_path: str) -> None:
        logging.info(f"Loading data from {file_path}")
        with open(file_path, "r") as file:
            data = json.load(file)

        for item in data:
            entity = Entity(item["name"], item["type"], item["description"])

            # Add relationships
            for relationship in item.get("relationships", []):
                entity.add_relationship(relationship["type"], relationship["target"])

            # Add all properties
            for prop, value in item.get("properties", {}).items():
                entity.set_property(prop, value)

            logging.info(f"Entity parsed: {entity}")
            self.entities[entity.name] = entity

        logging.info(f"Entities created: {self.entities.keys()}")

    def populate_graph(self) -> None:
        logging.info("Populating graph...")
        try:
            # Create or update entities
            self.db_operations.bulk_create_entities(self.entities.values())
            logging.info("Entities created/updated in the graph.")

            # Prepare relationships
            all_relationships = [
                {
                    "source": relationship.source.name,
                    "target": relationship.target,
                    "type": relationship.rel_type,
                }
                for entity in self.entities.values()
                for relationship in entity.relationships
            ]

            if not all_relationships:
                logging.info("No relationships to create.")
            else:
                logging.info(
                    f"Attempting to create {len(all_relationships)} relationships."
                )
                self.db_operations.bulk_create_relationships(all_relationships)
                logging.info("Relationships created in the graph.")
        except Exception as e:
            logging.error(f"Error populating graph: {e}")
            raise

    def query_graph(self, query: str, **params: Any) -> List[Dict[str, Any]]:
        return self.db_operations.db_manager.execute_query(query, **params)

    def clear_graph(self) -> None:
        self.db_operations.clear_graph()

    def __repr__(self) -> str:
        return f"World with {len(self.entities)} entities"

    # CLI commands

    def list_entities(
        self, type: str = None, name: str = None, description: str = None
    ) -> List[Dict[str, Any]]:
        entities = self.db_operations.query_entities(type, name, description)
        detailed_entities = []
        for entity in entities:
            all_properties = self.db_operations.get_entity_properties(entity["name"])
            core_properties = {
                k: v
                for k, v in all_properties.items()
                if k in ["name", "entity_type", "description"]
            }
            dynamic_properties = {
                k: v
                for k, v in all_properties.items()
                if k not in ["name", "entity_type", "description"]
            }
            detailed_entity = {
                **core_properties,
                "dynamic_properties": dynamic_properties,
            }
            detailed_entities.append(detailed_entity)
        return (
            detailed_entities
            if detailed_entities
            else "No entities found matching the criteria."
        )

    def list_relationships(
        self, source_type: str = None, rel_type: str = None, target_type: str = None
    ) -> List[Dict[str, Any]]:
        relationships = self.db_operations.query_relationships(
            source_type, rel_type, target_type
        )
        return relationships

    def add_relationship(
        self, source: str, rel_type: str, target: str, properties: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        source_entity = self.entities.get(source)
        target_entity = self.entities.get(target)
        if not source_entity:
            logging.error(f"Source entity '{source}' does not exist.")
            raise ValueError(f"Source entity '{source}' does not exist.")
        if not target_entity:
            logging.error(f"Target entity '{target}' does not exist.")
            raise ValueError(f"Target entity '{target}' does not exist.")
        created_relationship = self.db_operations.create_relationship(
            source, rel_type, target, properties
        )
        if created_relationship:
            source_entity.add_relationship(rel_type, target_entity, **properties or {})
            logging.info(
                f"Relationship '{rel_type}' added between '{source}' and '{target}'."
            )
        return created_relationship

    def add_entity(
        self, entity_type: str, name: str, description: str
    ) -> Dict[str, Any]:
        entity = Entity(name, entity_type, description)
        logging.info(f"Creating entity: {entity}")
        created_entity = self.db_operations.create_entity(entity)
        if created_entity:
            self.entities[name] = entity
            logging.info(f"Entity added to internal Dictionary: {self.entities[name]}")
        else:
            logging.error(f"Failed to create entity: {entity}")
        return dict(created_entity) if created_entity else None

    def modify_entity(
        self,
        name: str,
        new_name: str = None,
        entity_type: str = None,
        description: str = None,
    ) -> Dict[str, Any]:
        logging.info(
            f"Starting modify_entity for name: {name} with new_name: {new_name}, entity_type: {entity_type}, description: {description}"
        )

        updated_properties = self.get_updated_properties(
            new_name, entity_type, description
        )
        logging.info(f"Updated properties to be applied: {updated_properties}")

        updated_entity = self.update_entity_in_db(name, updated_properties)

        if updated_entity:
            self.update_entity_in_memory(name, new_name, updated_properties)

        return dict(updated_entity) if updated_entity else None

    def get_updated_properties(
        self, new_name: str, entity_type: str, description: str
    ) -> Dict[str, Any]:
        updated_properties = {}
        if new_name:
            updated_properties["name"] = new_name
        if entity_type:
            updated_properties["entity_type"] = entity_type
        if description:
            updated_properties["description"] = description
        return updated_properties

    def update_entity_in_db(
        self, name: str, updated_properties: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not hasattr(self.db_operations, "update_entity"):
            logging.error("db_operations object does not have update_entity method.")
            raise AttributeError(
                "update_entity method is not defined in db_operations."
            )

        try:
            updated_entity = self.db_operations.update_entity(name, updated_properties)
            logging.info(f"Update entity result: {updated_entity}")
        except Exception as e:
            logging.error(
                f"Error updating entity in database for name: {name} with updated_properties: {updated_properties}: {e}"
            )
            raise
        return updated_entity

    def update_entity_in_memory(
        self, name: str, new_name: str, updated_properties: dict[str, Any]
    ) -> None:
        try:
            if new_name:
                self.entities[new_name] = self.entities.pop(name, None)
                logging.info(
                    f"Updated internal entities dictionary: renamed {name} to {new_name}"
                )
        except Exception as e:
            logging.error(
                f"Error updating internal dictionary for renaming {name} to {new_name}: {e}"
            )
            raise

        try:
            if name in self.entities and self.entities[name]:
                logging.info(f"Entity before update: {self.entities[name]}")
                self.entities[name].__dict__.update(updated_properties)
                logging.info(
                    f"Updated properties in internal entities dictionary for {name}: {self.entities[name]}"
                )
        except Exception as e:
            logging.error(
                f"Error updating properties in internal entities dictionary for {name}: {e}"
            )
            raise

    def add_property(self, name: str, property_name: str, property_value: Any) -> str:
        entity = self.entities.get(name)
        if not entity:
            return f"Entity '{name}' not found."

        entity.set_property(property_name, property_value)
        updated_entity = self.db_operations.update_entity(
            name, {property_name: property_value}
        )

        if updated_entity:
            return f"Property '{property_name}' added to entity '{name}'."
        return f"Failed to add property '{property_name}' to entity '{name}'."

    def modify_property(self, name: str, property_name: str, new_value: Any) -> str:
        entity = self.entities.get(name)
        if not entity:
            return f"Entity '{name}' not found."

        if property_name not in entity.get_all_properties():
            return f"Property '{property_name}' does not exist for entity '{name}'."

        entity.set_property(property_name, new_value)
        updated_entity = self.db_operations.update_entity(
            name, {property_name: new_value}
        )

        if updated_entity:
            return f"Property '{property_name}' of entity '{name}' updated to '{new_value}'."
        return f"Failed to update property '{property_name}' of entity '{name}'."

    def delete_property(self, name: str, property_name: str) -> str:
        entity = self.entities.get(name)
        if not entity:
            return f"Entity '{name}' not found."

        if property_name not in entity.get_all_properties():
            return f"Property '{property_name}' does not exist for entity '{name}'."

        # Don't allow deletion of core properties
        if property_name in ["name", "entity_type", "description"]:
            return f"Cannot delete core property '{property_name}'."

        entity.delete_property(property_name)

        # Update the entity in the database
        updated_properties = entity.get_all_properties()
        updated_entity = self.db_operations.update_entity(name, updated_properties)

        if updated_entity:
            return f"Property '{property_name}' deleted from entity '{name}'."
        return f"Failed to delete property '{property_name}' from entity '{name}'."


class Command:
    def __init__(
        self,
        name: str,
        description: str,
        execute: Callable,
        arguments: Dict[str, Dict[str, str]] = None,
        aliases: List[str] = None,
    ):
        self.name = name
        self.description = description
        self.execute = execute
        self.arguments = arguments or {}
        self.aliases = aliases or []

    def __str__(self) -> str:
        return f"{self.name}, {self.description}, {self.execute}, {self.arguments}, Aliases: {self.aliases}"


class CLI:

    def __init__(self, world) -> None:
        self.completer = None
        self.session = None
        self.use_prompt_toolkit = False
        self.world = world
        self.commands: Dict[str, Command] = {}
        self.register_commands()
        self.setup_autocomplete()

    def setup_autocomplete(self):
        self.completer = WordCompleter(list(self.commands.keys()), ignore_case=True)
        try:
            self.session = PromptSession(completer=self.completer)
            self.use_prompt_toolkit = True
        except NoConsoleScreenBufferError:
            self.use_prompt_toolkit = False
            print(
                "Advanced console features not available. Falling back to basic input."
            )

    def register_command(
        self,
        name: str,
        description: str,
        execute: Callable,
        arguments: Dict[str, Dict[str, str]] = None,
        aliases: List[str] = None,
    ):
        arguments = arguments or {}
        aliases = aliases or []
        new_command = Command(name, description, execute, arguments, aliases)
        self.commands[name] = new_command
        for alias in aliases:
            self.commands[alias] = new_command
        logging.info(f"Command registered: {new_command}")

    def validate_argument_exists(self, arg_name: str, command_name: str) -> bool:
        if arg_name not in self.commands[command_name].arguments:
            logging.error(f"Invalid argument for command {command_name}: {arg_name}")
            return False
        return True

    def validate_argument_pattern(self, args: List[str]) -> bool:
        if not args:
            return True  # Allow commands without arguments

        i = 0
        while i < len(args):
            if args[i].startswith("--"):
                if i + 1 >= len(args):
                    logging.error(f"No value provided for argument {args[i]}")
                    return False

                # Move to the next argument
                i += 2
            else:
                logging.error(f"Argument {args[i]} does not start with '--'")
                return False

        return True

    def split_command_input(self, command_input: str) -> Tuple[str, List[str]]:
        # Normalize the command input to ensure consistent parsing
        command_input = command_input.strip()

        # Attempt to split the command input into command and argument parts
        try:
            command_name, args_string = command_input.split(" --", 1)
            args = shlex.split(
                "--" + args_string
            )  # Prepend '--' to ensure correct splitting
        except ValueError:
            # If splitting fails, assume the entire input is the command (no arguments)
            command_name = command_input
            args = []

        logging.info(f"DEBUG: Split command: name={command_name}, args={args}")
        return command_name, args

    def execute_command(self, command_input: str) -> None:
        logging.info(f"Start executing command: {command_input}")

        try:
            command_name, args = self.split_command_input(command_input)
            logging.info(f"Split command input into name: {command_name}, args: {args}")
        except ValueError as e:
            logging.error(f"Error parsing command: {e}")
            print(f"Error parsing command: {e}")
            return

        if not command_name:
            logging.error("Command name is empty after parsing.")
            print("Invalid command. Type 'help' for available commands.")
            return

        command = self.commands.get(command_name)
        if not command:
            # Check aliases if command is not found directly
            for cmd in self.commands.values():
                if command_name in cmd.aliases:
                    command = cmd
                    break

        if not command:
            logging.error(f"Unknown command: {command_name}")
            print(
                f"Unknown command: {command_name}. Type 'help' for available commands."
            )
            return

        if "--help" in args:
            self.print_command_help(command)
            return

        try:
            parsed_args = self.parse_arguments(args)

            if command.execute is None:
                logging.error(
                    f"Command execute method is None for command: {command_name}"
                )
            else:
                logging.info(
                    f"Executing command: {command_name} with arguments: {parsed_args}"
                )

            result = command.execute(
                **parsed_args
            )  # This is where the error might occur

            logging.info(f"Command execution result: {result}")

            self.display_result(result)
            logging.info(f"Command executed successfully: {command_name}")
        except Exception as e:
            logging.error(
                f"Error executing command '{command_name}' with args {parsed_args}: {e}"
            )
            print(f"Error executing command in execute_command method: {e}")

    def parse_arguments(self, args: List[str]) -> Dict[str, str]:
        parsed_args = {}
        i = 0
        while i < len(args):
            if args[i].startswith("--"):
                arg_name = args[i][2:]
                if i + 1 < len(args):
                    arg_value = args[i + 1]
                    parsed_args[arg_name] = arg_value
                    logging.info(f"Parsed argument: {arg_name} -> {arg_value}")
                    i += 2
                else:
                    logging.error(f"No value provided for argument {args[i]}")
                    raise ValueError(f"No value provided for argument {args[i]}")
            else:
                logging.error(f"Invalid argument format: {args[i]}")
                raise ValueError(f"Invalid argument format: {args[i]}")
        return parsed_args

    def run(self) -> None:
        print("Enter your command or type 'help' for instructions or 'exit' to quit.")
        while True:
            try:
                if self.use_prompt_toolkit:
                    command_input = self.session.prompt(
                        HTML("<ansiyellow>Command></ansiyellow> "),
                        completer=self.completer,
                    ).strip()
                else:
                    command_input = self.fallback_input("Command> ").strip()

                if command_input in ["exit"]:
                    break
                if command_input == "help":
                    self.print_help()
                    continue
                self.execute_command(command_input)
            except EOFError:
                break
        print("\nThanks for using Worldbuilder")

    def fallback_input(self, prompt_text):
        return input(prompt_text)

    def print_help(self) -> None:
        print("Available commands:")
        for name, command in self.commands.items():
            print(f"  {name}: {command.description}")
        print("\nFor detailed help on a specific command, type '<command_name> --help'")

    def print_command_help(self, command: Command) -> None:
        print(f"Command: {command.name}")
        print(f"Description: {command.description}")
        print("Usage:")
        usage = f"  {command.name}"
        for arg_name in command.arguments:
            usage += f" --{arg_name} <value>"
        print(usage)
        print("Arguments:")
        for arg_name, arg_params in command.arguments.items():
            print(f"  --{arg_name}: {arg_params.get('help', 'No description')}")
        if command.aliases:
            print(f"Aliases: {', '.join(command.aliases)}")
        print("\nUse --help with any command to see this help message.")

    def display_result(self, result: Any) -> None:
        if result is None:
            print("Operation completed, but no results were returned.")
        elif isinstance(result, str):
            print(result)
        elif isinstance(result, list):
            self.display_list_result(result)
        else:
            print(str(result))
        print("")

    def display_list_result(self, result_list: List[Any]) -> None:
        for item in result_list:
            self.display_item_result(item)
            print("")

    def display_item_result(self, item: Any) -> None:
        if isinstance(item, Dict) and "dynamic_properties" in item:
            self.display_dict_result(item)
        else:
            print(item)

    def display_dict_result(self, item_dict: Dict[str, Any]) -> None:
        print(f"Name: {item_dict.get('name')}")
        print(f"Type: {item_dict.get('entity_type')}")
        print(f"Description: {item_dict.get('description')}")
        if item_dict["dynamic_properties"]:
            print("Dynamic Properties:")
            for key, value in item_dict["dynamic_properties"].items():
                print(f"  {key}: {value}")

    def register_commands(self) -> None:
        self.register_command(
            "list_entities",
            "List entities in the world",
            self.world.list_entities,
            {
                "type": {
                    "help": "Type of entities to list, e.g., Character, Location, Artifact"
                },
                "name": {"help": "Filter entities by name or part of the name"},
                "description": {
                    "help": "Filter entities by description or part of the description"
                },
            },
            aliases=["le"],
        )

        self.register_command(
            "list_relationships",
            "List relationships in the world",
            self.world.list_relationships,
            {
                "source_type": {"help": "Type of source entities"},
                "rel_type": {"help": "Type of relationship"},
                "target_type": {"help": "Type of target entities"},
            },
            aliases=["lr"],
        )

        self.register_command(
            "add_entity",
            "Adds an entity to the world",
            self.world.add_entity,
            {
                "entity_type": {
                    "help": "Type of entity to add, e.g., Character, Location, Artifact"
                },
                "name": {"help": "Name of the entity to add"},
                "description": {"help": "Description of the entity to add"},
            },
            aliases=["ae"],
        )

        self.register_command(
            "modify_entity",
            "Edits an entity in the world",
            self.world.modify_entity,
            {
                "entity_type": {
                    "help": "New type of entity, e.g., Character, Location, Artifact"
                },
                "name": {"help": "Name of the entity to edit"},
                "new_name": {"help": "New name of the entity"},
                "description": {"help": "New description of the entity"},
            },
            aliases=["me"],
        )

        self.register_command(
            "add_relationship",
            "Adds a relationship between two entities",
            self.world.add_relationship,
            {
                "source": {"help": "Name of the source entity"},
                "rel_type": {"help": "Type of the relationship"},
                "target": {"help": "Name of the target entity"},
                "properties": {
                    "help": "Additional properties for the relationship (optional)"
                },
            },
            aliases=["ar"],
        )

        self.register_command(
            "add_property",
            "Adds a new property to an entity",
            self.world.add_property,
            {
                "name": {"help": "Name of the entity to add the property to"},
                "property_name": {"help": "Name of the new property"},
                "property_value": {"help": "Value of the new property"},
            },
            aliases=["ap"],
        )

        self.register_command(
            "modify_property",
            "Modifies an existing property of an entity",
            self.world.modify_property,
            {
                "name": {"help": "Name of the entity to modify the property of"},
                "property_name": {"help": "Name of the property to modify"},
                "new_value": {"help": "New value for the property"},
            },
            aliases=["mp"],
        )
        self.register_command(
            "delete_property",
            "Deletes an existing property from an entity",
            self.world.delete_property,
            {
                "name": {"help": "Name of the entity to delete the property from"},
                "property_name": {"help": "Name of the property to delete"},
            },
            aliases=["dp"],
        )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        filename="app.log",
        filemode="w",
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logging.info("---------------------------Application started")

    load_dotenv()

    db_uri = os.getenv("DB_URI")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")

    my_world = World(db_uri, db_user, db_password)
    my_world.clear_graph()

    data_path = "data/world_data.json"
    my_world.load_data(data_path)
    print(my_world)

    my_world.populate_graph()
    print("Graph populated!")

    cli = CLI(my_world)

    cli.run()
    logging.info("---------------------------Application ended")


if __name__ == "__main__":
    main()
