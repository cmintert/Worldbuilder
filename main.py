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
        self.db_manager = DatabaseManager(db_uri, db_user, db_password)
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
        query = f"CREATE (n:{entity.entity_type} {{name: $name, description: $description}})"
        params = {"name": entity.name, "description": entity.description}
        self.db_manager.execute_query(query, **params)
        logging.info(f"Added entity to graph: {entity}")

    def add_relationship_to_graph(self, source_node, rel_type, target_node):
        query = f"MATCH (a {{name: $source}}), (b {{name: $target}}) CREATE (a)-[:{rel_type}]->(b)"
        params = {"source": source_node["name"], "target": target_node["name"]}
        self.db_manager.execute_query(query, **params)
        logging.info(
            f"Added relationship to graph: {source_node['name']} -{rel_type}-> {target_node['name']}"
        )

    def populate_graph(self):
        logging.info("Populating graph...")
        try:
            for entity in self.entities.values():
                self.add_to_graph(entity)

            for entity in self.entities.values():
                for relationship in entity.relationships:
                    target_entity = self.entities[relationship.target.name]
                    self.add_relationship_to_graph(
                        {"name": entity.name},
                        relationship.rel_type,
                        {"name": target_entity.name},
                    )

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
            #print(
            #    f"Name: {node['name']} *** Type: {list(node.labels)[0]} *** Description: '{node['description']}'"
            #)
            entities.append({
                "name": node["name"],
                "type": list(node.labels)[0],
                "description": node["description"]
            })
        return entities

    def list_relationships(self, type=None, name=None, description=None):
        query_base = "MATCH (n"
        query_condition = f":{type}" if type else ""
        query_end = ")-[r]->(m) RETURN n, collect(type(r)) as rel_types, collect(m.name) as target_names"

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
        relationships = []
        for result in results:
            node = result["n"]
            relationship_details = ", ".join([f"{rel_type} -> {target_name}" for rel_type, target_name in
                                       zip(result["rel_types"], result["target_names"])])
            #print(
            #    f"Name: {node['name']} *** Type: {list(node.labels)[0]} *** Description: '{node['description']}' *** Relationships: {relationships}"
            #)
            relationships.append({
                "name": node["name"],
                "type": list(node.labels)[0],
                "description": node["description"],
                "relationships": relationship_details
            })
        return relationships

    def add_entity(self, type="not_set", name="not_set", description="not_set"):
        entity = Entity(name, type, description)
        self.entities[name] = entity
        self.add_to_graph(entity)
        print(f"Entity {name} added.")
        logging.info(f"Entity added: {entity}")

        return {
            "name": entity.name,
            "type": entity.entity_type,
            "description": entity.description
        }

    def modify_entity(self, name=None, new_name=None, type=None, description=None):
        if not name:
            raise ValueError("Name of the entity to modify is required.")

        entity = self.entities.get(name)
        if not entity:
            raise ValueError(f"Entity {name} not found.")

        # Update local entity details
        if new_name:
            entity.name = new_name
            self.entities[new_name] = self.entities.pop(name)
        if type:
            entity.entity_type = type
        if description:
            entity.description = description

        # Prepare and execute the Cypher query for updating the entity in the database
        query = """
        MATCH (n {name: $name})
        SET n.name = $new_name, n.description = $description, n.type = $type
        RETURN n
        """
        params = {"name": name, "new_name": new_name or name, "description": description or entity.description, "type": type or entity.entity_type}
        result = self.db_manager.execute_query(query, **params)

        if not result:
            raise ValueError(f"Failed to update entity {name} in the database.")

        logging.info(f"Entity {name} modified to {new_name if new_name else name}.")
        return {
            "name": new_name if new_name else name,
            "type": type or entity.entity_type,
            "description": description or entity.description
        }

class Command:
    def __init__(
        self, name: str, description: str, execute: Callable, arguments: Dict = None, aliases: List[str] = None
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

    def register_command(self, name, description, execute, arguments=None, aliases=None):
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
        if len(args) % 2 != 0:
            return False
        for i in range(0, len(args), 2):
            if not args[i].startswith("--") or args[i + 1].strip() == "":
                return False
        return True

    def split_command_input(self, command_input):
        parts = shlex.split(command_input)
        command_name = parts[0]
        args = parts[1:] if len(parts) > 1 else []
        return command_name, args

    def execute_command(self, command_input):

        logging.info(f"Start executing command: {command_input}")
        invalid_arg_present = False

        command_name, args = self.split_command_input(command_input)
        logging.info(f"Command name: {command_name}, args: {args}")
        if not self.validate_argument_pattern(args):
            print(
                "Invalid command pattern. Provide arguments in the format: --arg_name arg_value"
            )
            logging.error(
                "Invalid command pattern. Provide arguments in the format: --arg_name arg_value"
            )
            return

        if command_name in self.commands:
            command = self.commands[command_name]
            try:
                parsed_args = {}
                for i in range(0, len(args), 2):
                    if args[i].startswith("--"):
                        arg_name = args[i][2:]
                        # Check if the argument is valid. If not search for the next argument with a leading '--'
                        if not self.validate_argument_exists(arg_name, command_name):
                            invalid_arg_present = True

                        arg_value = args[i + 1] if i + 1 < len(args) else None
                        parsed_args[arg_name] = arg_value
                        logging.info(f"Parsed argument: {arg_name} -> {arg_value}")

                if not invalid_arg_present:
                    result = command.execute(**parsed_args)
                    self.display_result(result)
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
        aliases=["le"]
    )

    cli.register_command(
        "list_relationships",
        "List relationships in the world",
        my_world.list_relationships,
        {
            "type": {
                "help": "Type of entities to list, e.g., Character, Location, Artifact"
            },
            "name": {"help": "Filter entities by name or part of the name"},
            "description": {
                "help": "Filter entities by description or part of the description"
            },
        },
        aliases=["lr"]
    )

    cli.register_command(
        "add_entity",
        "Ads an entity to the world",
        my_world.add_entity,
        {
            "type": {
                "help": "Type of entity to add, e.g., Character, Location, Artifact"
            },
            "name": {"help": "Name of the entity to add"},
            "description": {
                "help": "Description of the entity to add"
            },
        },
        aliases=["ae"]
    )

    cli.register_command(
        "modify_entity",
        "Edits an entity in the world",
        my_world.modify_entity,
        {
            "type": {
                "help": "New type of entity, e.g., Character, Location, Artifact"
            },
            "name": {"help": "Name of the entity to edit"},
            "new_name":{"help": "New name of the entity"},
            "description": {
                "help": "New description of the entity"
            },
        },
        aliases=["me"]
    )

    cli.run()
    logging.info("---------------------------Application ended")


if __name__ == "__main__":
    main()
