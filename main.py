from __future__ import annotations

import os
import logging
import shlex
import json

from prompt_toolkit import PromptSession
from prompt_toolkit.output.win32 import NoConsoleScreenBufferError
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.completion import NestedCompleter


from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree

from dotenv import load_dotenv
from typing import Callable, Dict, List, Tuple, Any, Optional

from command_completer import CommandCompleter
from data_classes import Entity
from database_manager import DatabaseManager
from graph_database_ops import GraphDatabaseOperations
from worldbuilder_commands import register_commands


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

    def get_entity_details(self, name: str) -> Dict[str, Any]:
        entity = self.entities.get(name)
        if not entity:
            return None

        details = entity.get_all_properties()
        relationships = self.db_operations.read_relationships(name)
        details["relationships"] = relationships
        return details

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
            # Ensure the order of keys in the detailed_entity dictionary
            detailed_entity = {
                "name": core_properties.get("name"),
                "entity_type": core_properties.get("entity_type"),
                "description": core_properties.get("description"),
                "dynamic_properties": dynamic_properties,
            }
            detailed_entities.append(detailed_entity)
        return (
            detailed_entities
            if detailed_entities
            else "No entities found matching the criteria."
        )

    def get_entity_graph(self, name: str, depth: str = "3") -> Dict[str, Any]:
        entity = self.entities.get(name)

        if not entity:
            return None

        # Passing depth from a prompt returns a string, we need to convert it to an integer
        if depth.isdigit():
            self.depth: int = int(depth)
        else:
            raise ValueError("Depth should be a positive number")

        graph = {
            "name": entity.name,
            "type": entity.entity_type,
            "relationships": self._get_relationships_recursive(entity.name, self.depth),
        }
        return graph

    def _get_relationships_recursive(
        self, entity_name: str, depth: int = 2
    ) -> List[Dict[str, Any]]:

        if depth == 0:
            return []

        relationships = self.db_operations.read_relationships(entity_name)
        result = []

        for rel, target in relationships:
            target_entity = {
                "name": target["name"],
                "type": target["entity_type"],
                "relationships": self._get_relationships_recursive(
                    target["name"], depth - 1
                ),
            }
            result.append({"type": rel["original_type"], "target": target_entity})
        return result

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
        self,
        entity_type: str,
        name: str,
        description: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        if properties is None:
            properties = {}

        entity = Entity(name, entity_type, description, **properties)
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

    def create_rel_type_catalogue(self):

        rel_types = []
        for entity in self.entities.values():
            for rel in entity.relationships:
                rel_types.append(rel.rel_type)
        return list(set(rel_types))

    def create_entity_type_catalogue(self):

        entity_types = []
        for entity in self.entities.values():
            entity_types.append(entity.entity_type)
        return list(set(entity_types))

    def create_entity_name_catalogue(self):

        return list(self.entities.keys())


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
        self.aliases: Dict[str, str] = {}

        self.setup_autocomplete()
        self.console = Console()

        register_commands(self)

    def setup_autocomplete(self):
        completer = CommandCompleter(self)
        try:
            self.session = PromptSession(completer=completer)
            self.use_prompt_toolkit = True
        except NoConsoleScreenBufferError:
            self.use_prompt_toolkit = False
            print(
                "Advanced console features not available. Falling back to basic input."
            )

    def create_nested_completer(self):
        command_dict = {}
        for name, command in self.commands.items():
            arg_dict = {f"--{arg}": None for arg in command.arguments.keys()}
            command_dict[name] = arg_dict
        for alias, command_name in self.aliases.items():
            command_dict[alias] = command_dict[command_name]
        return NestedCompleter.from_nested_dict(command_dict)

    def register_command(
        self,
        name: str,
        description: str,
        execute: Callable[..., Any],
        arguments: Dict[str, Dict[str, str]] = None,
        aliases: List[str] = None,
    ):
        arguments = arguments or {}
        aliases = aliases or []
        new_command = Command(name, description, execute, arguments, aliases)
        self.commands[name] = new_command
        for alias in aliases:
            self.aliases[alias] = name
        logging.info(f"Command registered: {new_command}")

    def validate_argument_exists(self, arg_name: str, command_name: str) -> bool:
        if arg_name not in self.commands[command_name].arguments:
            logging.error(f"Invalid argument for command {command_name}: {arg_name}")
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
        parsed_args = {}

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

        if command_name in self.aliases:
            command_name = self.aliases[command_name]

        command = self.commands.get(command_name)

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

            if command_name == "view_entity":
                result = command.execute(**parsed_args)
                self.display_entity_details(result)
            elif command_name == "view_graph":
                result = command.execute(**parsed_args)
                depth = min(int(parsed_args.get("depth", 3)), 5)  # Limit max depth to 5
                self.display_entity_graph(result, max_depth=depth)
            else:
                result = command.execute(**parsed_args)
                self.display_result(result)

            logging.info(f"Command execution result: {result}")
            logging.info(f"Command executed successfully: {command_name}")

        except Exception as e:
            logging.error(
                f"Error executing command '{command_name}' with args {parsed_args}: {e}"
            )
            print(f"Error executing command in execute_command method: {e}")

    def parse_arguments(self, args: List[str]) -> Dict[str, Any]:
        parsed_args = {}
        i = 0
        while i < len(args):
            if args[i].startswith("--"):
                arg_name = args[i][2:]
                if arg_name == "properties":
                    properties = {}
                    i += 1
                    while i < len(args) and not args[i].startswith("--"):
                        key, value = args[i].split("=")
                        properties[key] = value
                        i += 1
                    parsed_args["properties"] = properties
                elif i + 1 < len(args):
                    arg_value = args[i + 1]
                    parsed_args[arg_name] = arg_value
                    i += 2
                else:
                    logging.error(f"No value provided for argument {args[i]}")
                    raise ValueError(f"No value provided for argument {args[i]}")
            else:
                logging.error(f"Invalid argument format: {args[i]}")
                raise ValueError(f"Invalid argument format: {args[i]}")
        return parsed_args

    def run(self):
        self.console.print(
            "Enter your command or type 'help' for instructions or 'exit' to quit.",
            style="bold green",
        )
        while True:
            try:
                if self.use_prompt_toolkit:
                    command_input = self.session.prompt(
                        HTML("<ansiyellow>Command></ansiyellow> ")
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
        self.console.print("\nThanks for using Worldbuilder", style="bold blue")

    def fallback_input(self, prompt_text):
        return input(prompt_text)

    def print_help(self) -> None:
        self.console.print("Available commands:", style="bold green")
        for name, command in self.commands.items():
            alias_str = (
                f" (aliases: {', '.join(command.aliases)})" if command.aliases else ""
            )
            self.console.print(f"  {name:<15} - {command.description}{alias_str}")
        self.console.print(
            "\nFor detailed help on a specific command, type <command_name> --help",
            style="italic",
        )

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
            self.console.print(
                "Operation completed, but no results were returned.", style="yellow"
            )
        elif isinstance(result, str):
            self.console.print(result)
        elif isinstance(result, list):
            self.display_list_result(result)
        else:
            self.console.print(str(result))
        self.console.print("")

    def display_list_result(self, result_list: List[Any]) -> None:
        if not result_list:
            self.console.print("No results to display.", style="yellow")
            return

        headers = []
        for item in result_list:
            if isinstance(item, dict):
                headers = list(item.keys())
                break

        if not headers:
            self.console.print("Unable to determine table structure.", style="yellow")
            return

        table = Table(show_header=True, header_style="bold magenta")
        for header in headers:
            table.add_column(header, style="dim", max_width=50)  # Limit column width

        for item in result_list:
            if isinstance(item, dict):
                table.add_row(*[str(item.get(header, "")) for header in headers])
            else:
                table.add_row(str(item), *["" for _ in range(len(headers) - 1)])

        self.console.print(table)

    def display_item_result(self, item: Any) -> None:
        if isinstance(item, dict) and "dynamic_properties" in item:
            self.display_dict_result(item)
        else:
            self.console.print(item)

    def display_dict_result(self, item_dict: Dict[str, Any]) -> None:
        panel = Panel(
            f"[bold]Name:[/bold] {item_dict.get('name')}\n"
            f"[bold]Type:[/bold] {item_dict.get('entity_type')}\n"
            f"[bold]Description:[/bold] {item_dict.get('description')}\n",
            title="Entity Details",
            expand=False,
        )
        self.console.print(panel)

        if item_dict["dynamic_properties"]:
            prop_table = Table(show_header=True, header_style="bold blue")
            prop_table.add_column("Property", style="dim")
            prop_table.add_column("Value", style="dim")
            for key, value in item_dict["dynamic_properties"].items():
                prop_table.add_row(str(key), str(value))
            self.console.print(prop_table)

    def display_entity_details(self, entity_details: Dict[str, Any]) -> None:
        if not entity_details:
            self.console.print("Entity not found.", style="bold red")
            return

        panel = Panel(
            f"[bold]Name:[/bold] {entity_details.get('name')}\n"
            f"[bold]Type:[/bold] {entity_details.get('entity_type')}\n"
            f"[bold]Description:[/bold] {entity_details.get('description')}\n",
            title="Entity Details",
            expand=False,
        )
        self.console.print(panel)

        prop_table = Table(show_header=True, header_style="bold blue")
        prop_table.add_column("Property", style="dim")
        prop_table.add_column("Value", style="dim")
        for key, value in entity_details.items():
            if key not in ["name", "entity_type", "description", "relationships"]:
                prop_table.add_row(str(key), str(value))
        self.console.print(prop_table)

        # New code to handle relationships
        if "relationships" in entity_details:
            rel_table = Table(show_header=True, header_style="bold green")
            rel_table.add_column("Relationship Type", style="dim")
            rel_table.add_column("Target Entity", style="dim")
            for rel in entity_details["relationships"]:
                rel_type = rel[0][
                    "original_type"
                ]  # Adjust based on your data structure
                target_name = rel[1]["name"]  # Adjust based on your data structure
                rel_table.add_row(rel_type, target_name)
            self.console.print("\nRelationships:", style="bold")
            self.console.print(rel_table)

    def display_entity_graph(self, graph: Dict[str, Any], max_depth: int = 3) -> None:
        if not graph:
            self.console.print("Entity not found.", style="bold red")
            return

        tree = Tree(f"[bold]{graph['name']}[/bold] ({graph['type']})")
        self._add_relationships_to_tree(
            tree, graph.get("relationships", []), current_depth=1, max_depth=max_depth
        )
        self.console.print(tree)

    def _add_relationships_to_tree(
        self,
        tree: Tree,
        relationships: List[Dict[str, Any]],
        current_depth: int,
        max_depth: int,
    ) -> None:
        if current_depth > max_depth:
            return

        for rel in relationships:
            rel_description = f"[italic]{rel['type']}[/italic] → [bold]{rel['target']['name']}[/bold] ({rel['target']['type']})"
            child = tree.add(rel_description)
            self._add_relationships_to_tree(
                child,
                rel["target"].get("relationships", []),
                current_depth + 1,
                max_depth,
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
    # exit
    # my_world.clear_graph()

    data_path = "data/world_data_v3.json"
    my_world.load_data(data_path)
    print(my_world)

    my_world.populate_graph()
    print("Graph populated!")

    cli = CLI(my_world)

    cli.run()
    logging.info("---------------------------Application ended")


if __name__ == "__main__":
    main()
