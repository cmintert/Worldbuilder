import os
import logging
import shlex
import textwrap

import pandas as pd
from py2neo import Graph
from dotenv import load_dotenv
from typing import Callable, Dict, List


class DatabaseManager:
    def __init__(self, db_uri, db_user, db_password):
        try:
            self.graph = Graph(db_uri, auth=(db_user, db_password))
        except Exception as e:
            logging.error(f"Error connecting to the database: {e}")
            raise

    def execute_query(self, query, **params):
        try:
            return self.graph.run(query, **params).data()
        except Exception as e:
            logging.error(f"Error executing query '{query}': {e}")
            raise


class GraphDatabaseOperations:
    def __init__(self, db_manager):
        self.db_manager = db_manager

    # Graph Operations

    def clear_graph(self):
        query = "MATCH (n) DETACH DELETE n"
        self.db_manager.execute_query(query)
        logging.info("Graph cleared.")

    # Entity Operations

    def create_entity(self, entity):
        query = """
        CREATE (n:Entity $properties)
        RETURN n
        """
        result = self.db_manager.execute_query(
            query, properties=entity.get_all_properties()
        )
        return result[0]["n"] if result else None

    def bulk_create_entities(self, entities):
        query = """
        UNWIND $entities AS entity
        CREATE (n:Entity)
        SET n = entity
        """
        self.db_manager.execute_query(
            query, entities=[entity.get_all_properties() for entity in entities]
        )

    def read_entity(self, name):
        query = """
        MATCH (n:Entity {name: $name})
        RETURN n
        """
        result = self.db_manager.execute_query(query, name=name)
        return result[0]["n"] if result else None

    def update_entity(self, name, updated_properties):
        query = """
        MATCH (n:Entity {name: $name})
        SET n += $properties
        RETURN n
        """
        result = self.db_manager.execute_query(
            query, name=name, properties=updated_properties
        )
        return result[0]["n"] if result else None

    def delete_entity(self, name):
        query = """
        MATCH (n:Entity {name: $name})
        DETACH DELETE n
        """
        self.db_manager.execute_query(query, name=name)

    # Relationship Operations

    def create_relationship(self, source_name, rel_type, target_name, properties=None):
        # Use an f-string to include the rel_type directly in the query
        query = f"""
        MATCH (a:Entity {{name: $source_name}}), (b:Entity {{name: $target_name}})
        CREATE (a)-[r:{rel_type}]->(b)
        SET r = $properties
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

    def bulk_create_relationships(self, relationships):
        for rel in relationships:
            query = f"""
            MATCH (a:Entity {{name: $source}}), (b:Entity {{name: $target}})
            CREATE (a)-[r:{rel['type']}]->(b)
            SET r = $properties
            """
            self.db_manager.execute_query(
                query,
                source=rel["source"],
                target=rel["target"],
                properties=rel["properties"],
            )

    def read_relationships(self, entity_name, rel_type=None):
        query = """
        MATCH (n:Entity {name: $name})-[r]->(m:Entity)
        WHERE $rel_type IS NULL OR type(r) = $rel_type
        RETURN r, m
        """
        result = self.db_manager.execute_query(
            query, name=entity_name, rel_type=rel_type
        )
        return [(r["r"], r["m"]) for r in result]

    def delete_relationship(self, source_name, rel_type, target_name):
        query = """
        MATCH (a:Entity {name: $source_name})-[r:$rel_type]->(b:Entity {name: $target_name})
        DELETE r
        """
        self.db_manager.execute_query(
            query, source_name=source_name, rel_type=rel_type, target_name=target_name
        )

    # Query Operations

    def query_entities(self, entity_type=None, name=None, description=None):
        query = """
        MATCH (n:Entity)
        WHERE ($entity_type IS NULL OR n.entity_type = $entity_type)
          AND ($name IS NULL OR n.name CONTAINS $name)
          AND ($description IS NULL OR n.description CONTAINS $description)
        RETURN n
        """
        result = self.db_manager.execute_query(
            query, entity_type=entity_type, name=name, description=description
        )
        return [r["n"] for r in result]

    def query_relationships(self, source_type=None, rel_type=None, target_type=None):
        query = """
        MATCH (a:Entity)-[r]->(b:Entity)
        WHERE ($source_type IS NULL OR a.entity_type = $source_type)
          AND ($rel_type IS NULL OR type(r) = $rel_type)
          AND ($target_type IS NULL OR b.entity_type = $target_type)
        RETURN a, r, b
        """
        result = self.db_manager.execute_query(
            query, source_type=source_type, rel_type=rel_type, target_type=target_type
        )
        return [(r["a"], r["r"], r["b"]) for r in result]


class Entity:
    def __init__(self, name, entity_type, description=None, **properties):
        self._properties = {
            "name": name,
            "entity_type": entity_type,
            "description": description,
        }
        self._properties.update(properties)
        self.relationships = []

    def __getattr__(self, name):
        return self._properties.get(name)

    def __setattr__(self, name, value):
        if name in ["_properties", "relationships"]:
            super().__setattr__(name, value)
        else:
            self._properties[name] = value

    def get_property(self, name):
        return self._properties.get(name)

    def set_property(self, name, value):
        self._properties[name] = value

    def delete_property(self, name):
        if name not in ["name", "entity_type", "description"]:
            self._properties.pop(name, None)

    def get_all_properties(self):
        return self._properties.copy()

    def add_relationship(self, rel_type, target, **properties):
        relationship = Relationship(self, rel_type, target, **properties)
        self.relationships.append(relationship)
        return relationship

    def __repr__(self):
        return f"Entity(name={self.name}, type={self.entity_type})"


class Relationship:
    def __init__(self, source, rel_type, target, **properties):
        self._properties = {"source": source, "rel_type": rel_type, "target": target}
        self._properties.update(properties)

    def __getattr__(self, name):
        return self._properties.get(name)

    def __setattr__(self, name, value):
        if name == "_properties":
            super().__setattr__(name, value)
        else:
            self._properties[name] = value

    def get_property(self, name):
        return self._properties.get(name)

    def set_property(self, name, value):
        self._properties[name] = value

    def delete_property(self, name):
        if name not in ["source", "rel_type", "target"]:
            self._properties.pop(name, None)

    def get_all_properties(self):
        return self._properties.copy()

    def __repr__(self):
        return f"{self.source.name} -> {self.rel_type} -> {self.target.name}"


class World:
    def __init__(self, db_uri, db_user, db_password):
        self.db_manager = DatabaseManager(db_uri, db_user, db_password)
        self.db_operations = GraphDatabaseOperations(self.db_manager)
        self.entities = {}

    def load_data(self, file_path):
        df = pd.read_csv(file_path)
        for _, row in df.iterrows():
            entity = Entity(row["name"], row["type"], row["description"])
            for column in df.columns:
                if column not in ["name", "type", "description", "relationships"]:
                    entity.set_property(column, row[column])
            self.db_operations.create_entity(entity)
            self.entities[entity.name] = entity

        for _, row in df.iterrows():
            entity = self.entities[row["name"]]
            if row["relationships"] != "[]":
                relationships = eval(row["relationships"])
                for rel in relationships:
                    rel_type, rel_target = rel.split(":")
                    target_entity = self.entities.get(rel_target)
                    if target_entity:
                        self.db_operations.create_relationship(
                            entity.name, rel_type, target_entity.name
                        )

    def populate_graph(self):
        logging.info("Populating graph...")
        try:
            self.db_operations.bulk_create_entities(self.entities.values())

            all_relationships = [
                {
                    "source": relationship.source.name,
                    "target": relationship.target.name,
                    "type": relationship.rel_type,
                    "properties": relationship.get_all_properties(),
                }
                for entity in self.entities.values()
                for relationship in entity.relationships
            ]
            self.db_operations.bulk_create_relationships(all_relationships)

            logging.info("Graph population completed successfully")
        except Exception as e:
            logging.error(f"Error populating graph: {e}")
            raise

    def query_graph(self, query, **params):
        return self.db_operations.db_manager.execute_query(query, **params)

    def clear_graph(self):
        self.db_operations.clear_graph()

    def __repr__(self):
        return f"World with {len(self.entities)} entities"

    # CLI commands

    def list_entities(self, type=None, name=None, description=None):
        entities = self.db_operations.query_entities(type, name, description)
        return [dict(entity) for entity in entities]

    def list_relationships(self, source_type=None, rel_type=None, target_type=None):
        relationships = self.db_operations.query_relationships(
            source_type, rel_type, target_type
        )
        return (
            [
                {
                    "source": rel["source"],
                    "relationship": rel["relationship"],
                    "target": rel["target"],
                }
                for rel in relationships
            ]
            if relationships
            else []
        )

    def add_relationship(self, source, rel_type, target, properties=None):
        source_entity = self.entities.get(source)
        target_entity = self.entities.get(target)
        if not source_entity or not target_entity:
            return None
        created_relationship = self.db_operations.create_relationship(
            source, rel_type, target, properties
        )
        if created_relationship:
            source_entity.add_relationship(rel_type, target_entity, **properties or {})
        return created_relationship

    def add_entity(self, entity_type, name, description):
        entity = Entity(name, entity_type, description)
        created_entity = self.db_operations.create_entity(entity)
        if created_entity:
            self.entities[name] = entity
        return dict(created_entity) if created_entity else None

    def modify_entity(self, name, new_name=None, entity_type=None, description=None):
        updated_properties = {}
        if new_name:
            updated_properties["name"] = new_name
        if entity_type:
            updated_properties["entity_type"] = entity_type
        if description:
            updated_properties["description"] = description

        updated_entity = self.db_operations.update_entity(name, updated_properties)
        if updated_entity:
            if new_name:
                self.entities[new_name] = self.entities.pop(name, None)
            if name in self.entities:
                self.entities[name].update(updated_properties)
        return dict(updated_entity) if updated_entity else None


class Command:
    def __init__(
        self,
        name: str,
        description: str,
        execute: Callable,
        arguments: Dict = None,
        aliases: List[str] = None,
    ):
        self.name = name
        self.description = description
        self.execute = execute
        self.arguments = arguments or {}
        self.aliases = aliases or []

    def __str__(self):
        return f"{self.name}, {self.description}, {self.execute}, {self.arguments}, Aliases: {self.aliases}"


class CLI:

    def __init__(self, world):
        self.world = world
        self.commands = {}
        self.register_commands()

    def register_command(
        self, name, description, execute, arguments=None, aliases=None
    ):
        arguments = arguments or {}
        aliases = aliases or []
        new_command = Command(name, description, execute, arguments, aliases)
        self.commands[name] = new_command
        for alias in aliases:
            self.commands[alias] = new_command
        logging.info(f"Command registered: {new_command}")

    def validate_argument_exists(self, arg_name, command_name):
        if arg_name not in self.commands[command_name].arguments:
            logging.error(f"Invalid argument for command {command_name}: {arg_name}")
            return False
        return True

    def validate_argument_pattern(self, args):
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

    def split_command_input(self, command_input):
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

    def execute_command(self, command_input):
        logging.info(f"Start executing command: {command_input}")

        command_name, args = self.split_command_input(command_input)
        logging.info(f"DEBUG: Parsed command: name={command_name}, args={args}")

        if not command_name:
            print("Invalid command. Type 'help' for available commands.")
            return

        # Check for both the full command name and its aliases
        if command_name in self.commands or any(
            command_name == alias
            for command in self.commands.values()
            for alias in command.aliases
        ):
            command = self.commands.get(command_name) or next(
                cmd for cmd in self.commands.values() if command_name in cmd.aliases
            )
            try:
                parsed_args = {}
                i = 0
                while i < len(args):
                    if args[i].startswith("--"):
                        arg_name = args[i][2:]  # Remove '--' prefix
                        if i + 1 < len(args):
                            arg_value = args[i + 1]
                            parsed_args[arg_name] = arg_value
                            i += 2
                        else:
                            parsed_args[arg_name] = None
                            i += 1
                    else:
                        i += 1
                    logging.info(f"DEBUG: Parsed argument: {arg_name} -> {arg_value}")

                result = command.execute(**parsed_args)
                self.display_result(result)
                logging.info(f"Command executed: {command_name}")
            except Exception as e:
                logging.error(f"Error executing command: {e}")
                print(f"Error executing command: {e}")
        else:
            logging.error(f"Unknown command: {command_name}")
            print(f"Unknown command: {command_name}")

    def run(self):
        print("Enter your command or type 'help' for instructions or 'exit' to quit.")
        while True:
            command_input = input("Command> ").strip()
            if command_input in ["exit"]:
                break
            if command_input == "help":
                self.print_help()
                continue
            self.execute_command(command_input)

    def print_help(self):
        print("Available commands:")
        for name, command in self.commands.items():
            print(f"  {name}: {command.description}")
            if command.arguments:
                for arg_name, arg_params in command.arguments.items():
                    print(
                        f"    --{arg_name}: {arg_params.get('help', 'No description')}"
                    )

    def display_result(self, result):
        if isinstance(result, list):
            for item in result:
                wrapped_text = textwrap.wrap(str(item), width=120)
                for line in wrapped_text:
                    print(line)
                print("")
        else:
            wrapped_text = textwrap.wrap(str(result), width=120)
            for line in wrapped_text:
                print(line)
            print("")

    def register_commands(self):
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


def main():
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

    data_path = "data/world_data.csv"
    my_world.load_data(data_path)
    print(my_world)

    my_world.populate_graph()
    print("Graph populated!")

    cli = CLI(my_world)

    cli.run()
    logging.info("---------------------------Application ended")


if __name__ == "__main__":
    main()
