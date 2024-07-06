import os
import argparse
import logging
import pandas as pd
from py2neo import Graph, Node, Relationship as Neo4jRelationship
from py2neo.errors import ClientError
from dotenv import load_dotenv

class Entity:
    def __init__(self, entity_id, name, entity_type, description):
        self.entity_id = entity_id
        self.name = name
        self.entity_type = entity_type
        self.description = description
        self.relationships = []

    def add_relationship(self, relationship):
        self.relationships.append(relationship)

    def __repr__(self):
        return f'{self.entity_id}: {self.name}, of the type {self.entity_type}'

class Relationship:
    def __init__(self, rel_type, target):
        self.rel_type = rel_type
        self.target = target

    def __repr__(self):
        return f'{self.rel_type} -> {self.target.name}'

class World:
    def __init__(self, db_uri, db_user, db_password):
        self.graph = Graph(db_uri, auth=(db_user, db_password))
        self.entities = {}

    def load_data(self, file_path):
        df = pd.read_csv(file_path)
        for index, row in df.iterrows():
            entity = Entity(row["id"], row["name"], row["type"], row["description"])
            self.entities[entity.entity_id] = entity

        for index, row in df.iterrows():
            entity = self.entities[row["id"]]
            for rel in eval(row["relationships"]):
                rel_type, rel_target = rel.split(":")
                target_entity = next((e for e in self.entities.values() if e.name == rel_target), None)
                if target_entity:
                    relationship = Relationship(rel_type, target_entity)
                    entity.add_relationship(relationship)

    def populate_graph(self):
        nodes = {}
        for entity in self.entities.values():
            node = Node(entity.entity_type, name=entity.name, description=entity.description)
            self.graph.create(node)
            nodes[entity.entity_id] = node

        for entity in self.entities.values():
            node = nodes[entity.entity_id]
            for rel in entity.relationships:
                target_node = nodes.get(rel.target.entity_id)
                if target_node:
                    neo4j_rel = Neo4jRelationship(node, rel.rel_type, target_node)
                    self.graph.create(neo4j_rel)

    def query_graph(self, query):
        try:
            result = self.graph.run(query).data()
            logging.info(f"Query successful: {query}")
            return result
        except ClientError as e:
            logging.error(f"Query syntax error: {e}")
            raise ClientError(e.message)
        except Exception as e:
            logging.error(f"Error executing query '{query}': {e}")
            raise

    def clear_graph(self):
        self.graph.run("MATCH (n) DETACH DELETE n")
        print("*** Whole Graph deleted ***")

    def __repr__(self):
        return f"World with {len(self.entities)} entities"



class CLI:
    def __init__(self, world):
        self.world = world

    def format_results(self, results):
        if not results:
            return "No results found or query execution error."
        formatted = "\n".join([str(record) for record in results])
        return formatted

    def display_help(self):
        help_text = """
        Welcome to the Interactive Cypher Query CLI!
        
        Commands:
        - Type 'exit' to quit the CLI.
        - Type 'help' to display this help message.
        - Type 'cypher' to enter a CYPHER query.
        
        Cypher
        - Type 'EXECUTE' on a new line to execute the query.
        - Typing 'EXECUTE' on an empty query wil drop you back to command mode.
        
        Example Query:
        MATCH (n)
        RETURN labels(n) AS labels, n.name AS name
        EXECUTE
        """
        print(help_text)

    def get_query_from_user(self):
        query_lines = []
        print("Start typing your Cypher query. Type 'EXECUTE' on a new line to execute the query.")
        while True:
            try:
                line = input("Cypher> ")
                if line.strip().upper() == "EXECUTE" or line.strip().upper() == "EX":
                    break
                query_lines.append(line)
                print(f"Current query:\n{' '.join(query_lines)}")
            except Exception as e:
                print(f"Error while reading input: {e}")
        query = "\n".join(query_lines).strip()
        return query

    def execute_query(self, query):
        if not query:
            print("No query entered. Please try again.")
            return
        print(f"Executing query:\n{query}")
        try:
            results = self.world.query_graph(query)
            print(self.format_results(results))
        except ClientError as e:
            print(f"Syntax error in query: {e.message}")
        except Exception as e:
            print(f"Error executing query: {e}")

    def run(self):
        print("Enter your command or hit return to start queueing CYPHER commands:")
        print("Type 'help' for instructions or 'exit' to quit.")

        while True:
            try:
                command = input("Command> ").strip().lower()
                if command == "exit":
                    print("Exiting CLI.")
                    break
                elif command == "help":
                    self.display_help()
                elif command == "cypher":
                    query = self.get_query_from_user()
                    self.execute_query(query)

            except Exception as e:
                print(f"Unexpected error: {e}")



def main():

    # Configure logging
    logging.basicConfig(level=logging.INFO, filename='app.log', filemode='w',
                        format='%(name)s - %(levelname)s - %(message)s')

    # Load environment variables
    load_dotenv()

    # Database credentials
    db_uri = os.getenv("DB_URI")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")

    # Initialize the world
    my_world = World(db_uri, db_user, db_password)

    # Clear the graph
    my_world.clear_graph()

    # Load data from CSV
    data_path = "data/world_data.csv"
    my_world.load_data(data_path)
    print(my_world)

    # Populate Neo4j graph database
    my_world.populate_graph()
    print("Graph populated!")

    # Start CLI
    cli = CLI(my_world)
    cli.run()

if __name__ == "__main__":
    main()
