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
        self.graph = Graph(db_uri, auth=(db_user, db_password))

    def clear_graph(self):
        self.graph.run("MATCH (n) DETACH DELETE n")
        logging.info("Graph cleared")

    def execute_query(self, query, **params):
        try:
            return self.graph.run(query, **params).data()
        except Exception as e:
            logging.error(f"Error executing query '{query}': {e}")
            raise


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
        self.entities = {}

    def load_data(self, file_path):
        df = pd.read_csv(file_path)
        for _, row in df.iterrows():
            entity = Entity(row["name"], row["type"], row["description"])
            for column in df.columns:
                if column not in ["name", "type", "description", "relationships"]:
                    entity.set_property(column, row[column])
            self.entities[entity.name] = entity

        for _, row in df.iterrows():
            entity = self.entities[row["name"]]
            if row["relationships"] != "[]":
                relationships = eval(row["relationships"])
                for rel in relationships:
                    rel_type, rel_target = rel.split(":")
                    target_entity = self.entities.get(rel_target)
                    if target_entity:
                        entity.add_relationship(rel_type, target_entity)

    def add_to_graph(self, entity):
        properties = entity.get_all_properties()
        query = f"CREATE (n:{entity.entity_type} $properties)"
        self.db_manager.execute_query(query, properties=properties)
        logging.info(f"Added entity to graph: {entity}")

    def add_relationship_to_graph(self, relationship):
        query = f"""
        MATCH (a {{name: $source_name}}), (b {{name: $target_name}})
        CREATE (a)-[r:{relationship.rel_type} $properties]->(b)
        """
        properties = relationship.get_all_properties()
        source_name = properties.pop("source").name
        target_name = properties.pop("target").name
        rel_type = properties.pop("rel_type")
        self.db_manager.execute_query(
            query,
            source_name=source_name,
            target_name=target_name,
            properties=properties,
        )
        logging.info(f"Added relationship to graph: {relationship}")

    def populate_graph(self):
        logging.info("Populating graph...")
        try:
            for entity in self.entities.values():
                self.add_to_graph(entity)

            for entity in self.entities.values():
                for relationship in entity.relationships:
                    self.add_relationship_to_graph(relationship)

            logging.info("Graph population completed successfully")
        except Exception as e:
            logging.error(f"Error populating graph: {e}")
            raise

    def query_graph(self, query):
        return self.db_manager.execute_query(query)

    def clear_graph(self):
        self.db_manager.clear_graph()

    def __repr__(self):
        return f"World with {len(self.entities)} entities"

    # CLI commands

    def list_entities(self, type=None, name=None, description=None):
        query_base = "MATCH (n"
        query_condition = f":{type}" if type else ""
        query_end = ") RETURN n"

        conditions = []
        if name:
            conditions.append(f"n.name CONTAINS '{name}'")
        if description:
            conditions.append(f"n.description CONTAINS '{description}'")

        if conditions:
            query_end = " WHERE " + " AND ".join(conditions) + query_end

        query = f"{query_base}{query_condition}{query_end}"
        logging.info(f"Query executed for list_entities command: {query}")

        results = self.db_manager.execute_query(query)

        entities = []

        for result in results:
            node = result["n"]
            entities.append(dict(node))  # This will include all properties of the node
        return entities

    def list_relationships(self, type=None, name=None, description=None):
        query_base = "MATCH (n"
        query_condition = f":{type}" if type else ""
        # RED: Update query to return relationship properties
        query_end = ")-[r]->(m) RETURN n, r, m, properties(r) as rel_props"

        conditions = []
        if name:
            conditions.append(f"n.name CONTAINS '{name}'")
        if description:
            conditions.append(f"n.description CONTAINS '{description}'")

        if conditions:
            query_end = " WHERE " + " AND ".join(conditions) + query_end

        query = f"{query_base}{query_condition}{query_end}"
        logging.info(f"Query executed for list_relationships command: {query}")

        results = self.db_manager.execute_query(query)
        relationships = []
        for result in results:
            source = dict(result["n"])
            relationship = dict(result["r"])
            target = dict(result["m"])
            # RED: Include custom relationship properties
            rel_props = result["rel_props"]
            relationships.append(
                {
                    "source": source,
                    "relationship": {**relationship, **rel_props},
                    "target": target,
                }
            )
        return relationships

    def add_relationship(self, source, rel_type, target, properties=None):
        # RED: Changed parameter names to match CLI command
        source_entity = self.entities.get(source)
        target_entity = self.entities.get(target)
        if not source_entity or not target_entity:
            raise ValueError("Source or target entity not found.")

        props = eval(properties) if properties else {}
        relationship = source_entity.add_relationship(rel_type, target_entity, **props)
        self.add_relationship_to_graph(relationship)
        return f"Relationship added: {source} -{rel_type}-> {target} with properties: {props}"

    def add_entity(self, entity_type="not_set", name="not_set", description="not_set"):
        entity = Entity(name, entity_type, description)
        self.entities[name] = entity
        self.add_to_graph(entity)
        print(f"Entity {name} added.")
        logging.info(f"Entity added: {entity}")

        return {
            "name": entity.name,
            "entity_type": entity.entity_type,
            "description": entity.description,
        }


def modify_entity(self, name=None, new_name=None, entity_type=None, description=None):
    if not name:
        raise ValueError("Name of the entity to modify is required.")

    entity = self.entities.get(name)
    if not entity:
        raise ValueError(f"Entity {name} not found.")

    # Update local entity details
    if new_name:
        entity.name = new_name
        self.entities[new_name] = self.entities.pop(name)
    if entity_type:
        entity.entity_type = entity_type
    if description:
        entity.description = description

    # Prepare and execute the Cypher query for updating the entity in the database
    query = """
    MATCH (n {name: $old_name})
    SET n = $properties
    RETURN n
    """
    properties = {
        "name": new_name or name,
        "entity_type": entity_type or entity.entity_type,
        "description": description or entity.description,
    }
    params = {"old_name": name, "properties": properties}
    result = self.db_manager.execute_query(query, **params)

    if not result:
        raise ValueError(f"Failed to update entity {name} in the database.")

    logging.info(f"Entity {name} modified to {new_name if new_name else name}.")
    return {
        "name": new_name if new_name else name,
        "entity_type": entity_type or entity.entity_type,
        "description": description or entity.description,
    }


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
                "type": {
                    "help": "Type of entities to list, e.g., Character, Location, Artifact"
                },
                "name": {"help": "Filter entities by name or part of the name"},
                "description": {
                    "help": "Filter entities by description or part of the description"
                },
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
