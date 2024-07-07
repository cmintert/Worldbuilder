import os
import logging
import shlex

import pandas as pd
from py2neo import Graph, Node, Relationship as Neo4jRelationship
from py2neo.errors import ClientError
from dotenv import load_dotenv
from typing import Dict, Callable, Optional
import typer


class Entity:
    def __init__(self, name, entity_type, description):
        self.name = name
        self.entity_type = entity_type
        self.description = description
        self.relationships = []

    def __repr__(self):
        return f"{self.name}: {self.entity_type}"


class Relationship:
    def __init__(self, source, rel_type, target):
        self.source = source
        self.rel_type = rel_type
        self.target = target

    def __repr__(self):
        return f"{self.rel_type} -> {self.target.name}"


class RelationshipInfo:
    def __init__(self, rel_type, target):
        self.rel_type = rel_type
        self.target = target

    def __repr__(self):
        return f"{self.rel_type} -> {self.target.name}"


class World:
    def __init__(self, db_uri, db_user, db_password):
        self.graph = Graph(db_uri, auth=(db_user, db_password))
        self.entities = {}

    def load_data(self, file_path):
        df = pd.read_csv(file_path)
        for _, row in df.iterrows():
            entity = Entity(row["name"], row["type"], row["description"])

            self.entities[entity.name] = entity
            logging.info(f"Loaded entity: {entity}")

        for _, row in df.iterrows():
            entity = self.entities[row["name"]]
            if row["relationships"] != "[]":
                relationships = eval(row["relationships"])
                for rel in relationships:
                    rel_type, rel_target = rel.split(":")
                    target_entity = self.entities.get(rel_target)
                    if target_entity:
                        relationship = RelationshipInfo(rel_type, target_entity)
                        entity.relationships.append(relationship)
                        logging.info(
                            f"Loaded relationship: {relationship} to entity: {entity}"
                        )

    def add_to_graph(self, entity):
        try:
            node = Node(
                entity.entity_type, name=entity.name, description=entity.description
            )
            self.graph.create(node)
            logging.info(f"Added entity to graph: {entity}")
            return node
        except Exception as e:
            logging.error(f"Error adding entity to graph: {e}")
            raise

    def add_relationship_to_graph(self, source_node, rel_type, target_node):
        try:
            relationship = Neo4jRelationship(source_node, rel_type, target_node)
            self.graph.create(relationship)
            logging.info(
                f"Added relationship to graph: {source_node['name']} -{rel_type}-> {target_node['name']}"
            )
        except Exception as e:
            logging.error(f"Error adding relationship to graph: {e}")
            raise

    def populate_graph(self):
        logging.info("Populating graph...")
        tx = self.graph.begin()
        try:
            nodes = {}
            for entity in self.entities.values():
                node = self.add_to_graph(entity)
                nodes[entity.name] = node

            for entity in self.entities.values():
                source_node = nodes[entity.name]
                for relationship in entity.relationships:
                    target_node = nodes[relationship.target.name]
                    self.add_relationship_to_graph(
                        source_node, relationship.rel_type, target_node
                    )

            self.graph.commit(tx)
            logging.info("Graph population completed successfully")
        except Exception as e:
            tx.rollback()
            logging.error(f"Error populating graph: {e}")
            raise

    def query_graph(self, query):
        try:
            result = self.graph.run(query).data()
            logging.info(f"Query successful: {query}")
            return result
        except ClientError as e:
            logging.error(f"Query syntax error: {e}")
            raise
        except Exception as e:
            logging.error(f"Error executing query '{query}': {e}")
            raise

    def clear_graph(self):
        self.graph.run("MATCH (n) DETACH DELETE n")
        logging.info("Graph cleared")

    def list_entities(self, type=None, name=None, description=None):
        query_base = "MATCH (n"
        query_condition = f":{type}" if type else ""
        query_end = ")"

        conditions = []
        if name:
            conditions.append(f"n.name CONTAINS '{name}'")
        if description:
            conditions.append(f"n.description CONTAINS '{description}'")

        if conditions:
            query_end += " WHERE " + " AND ".join(conditions)

        query_end += " RETURN n"

        query = f"{query_base}{query_condition}{query_end}"
        logging.info(f"Query executed for list_entities command: {query}")
        try:
            results = self.graph.run(query).data()
            for result in results:
                node = result["n"]
                print(
                    f"({node['name']}:{list(node.labels)[0]} {{description: '{node['description']}'}})"
                )
        except ClientError as e:
            logging.error(f"Query syntax error: {e}")
            print(f"Query syntax error: {e}")
        except Exception as e:
            logging.error(f"Error executing query '{query}': {e}")
            print(f"Error executing query: {e}")

    def __repr__(self):
        return f"World with {len(self.entities)} entities"


class Command:
    def __init__(
        self, name: str, description: str, execute: Callable, arguments: Dict = None
    ):
        self.name = name
        self.description = description
        self.execute = execute
        self.arguments = arguments

    def __str__(self):
        return f"{self.name}, {self.description}, {self.execute}, {self.arguments}"


class CLI:
    def __init__(self, world):
        self.world = world
        self.commands = {}

    def register_command(self, name, description, execute, arguments=None):
        arguments = arguments or {}
        new_command = Command(name, description, execute, arguments)
        self.commands[name] = new_command
        logging.info(f"Command registered: {new_command}")

    def validate_argument(self, arg_name, command_name):
        if arg_name not in self.commands[command_name].arguments:
            logging.error(f"Invalid argument for command {command_name}: {arg_name}")
            return False
        return True

    def validate_argument_pattern(self, command_input):
        parts = shlex.split(command_input)
        # Exclude the command itself for the pattern check
        args = parts[1:]

        # Check for even number of elements in args (excluding command)
        if len(args) % 2 != 0:
            return False

        for i in range(0, len(args), 2):
            # Check if the argument name starts with `--`
            if not args[i].startswith("--"):
                return False
            # Check if the argument value is not empty
            if i + 1 >= len(args) or args[i + 1].strip() == "":
                return False

        return True

    def execute_command(self, command_input):
        parts = shlex.split(command_input)
        logging.info(f"Start executing command: {command_input}")
        logging.info(f"Parts of the command to be executed: {parts}")

        if not self.validate_argument_pattern(command_input):
            print(
                "Invalid command pattern. Please provide arguments in the format: --arg_name arg_value"
            )
            logging.error(
                "Invalid command pattern. Please provide arguments in the format: --arg_name arg_value"
            )
            return

        command_name = parts[0]
        args = parts[1:] if len(parts) > 1 else []
        logging.info(f"Command name: {command_name}, args: {args}")

        invalid_arg_present = False

        if command_name in self.commands:
            command = self.commands[command_name]
            try:
                parsed_args = {}
                for i in range(0, len(args), 2):
                    if args[i].startswith("--"):
                        arg_name = args[i][2:]
                        # Check if the argument is valid. If not search for the next argument with a leading '--'
                        if not self.validate_argument(arg_name, command_name):
                            invalid_arg_present = True

                        arg_value = args[i + 1] if i + 1 < len(args) else None
                        parsed_args[arg_name] = arg_value
                        logging.info(f"Parsed argument: {arg_name} -> {arg_value}")

                if not invalid_arg_present:
                    command.execute(**parsed_args)
                    logging.info(f"Command executed: {command_name}")
                else:
                    logging.error(
                        f"Invalid argument present for command: {command_name}. Command ABORTED!"
                    )
                    print(
                        f"Invalid argument present for command: {command_name}. Command ABORTED!"
                    )

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


def main():
    logging.basicConfig(
        level=logging.INFO,
        filename="app.log",
        filemode="a",
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

    cli.register_command(
        "list_entities",
        "List entities in the world",
        my_world.list_entities,
        {
            "type": {
                "help": "Type of entities to list, e.g., Character, Location, Artifact"
            },
            "name": {"help": "Filter entities by name or part of the name"},
            "description": {
                "help": "Filter entities by description or part of the description"
            },
        },
    )

    cli.run()
    logging.info("---------------------------Application ended")


if __name__ == "__main__":
    main()
