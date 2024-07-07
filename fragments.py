def list_relationships(self):
    query = "MATCH ()-[r]->() RETURN DISTINCT type(r) AS type, count(r) AS count"
    results = self.graph.run(query).data()
    for result in results:
        print(f"Relationship type: {result['type']}, Count: {result['count']}")


def list_relationships_for_entity(self, entity_name):
    query = f"MATCH (n {{name: '{entity_name}'}})-[r]->(m) RETURN r, m"
    results = self.graph.run(query).data()
    for result in results:
        print(f"{entity_name} {result['r'].type} {result['m']['name']}")


def add_entity(self, name, entity_type, description):
    if name not in self.entities:
        entity = Entity(name, entity_type, description)
        self.entities[name] = entity
        node = self.add_to_graph(entity)
        print(f"Entity {name} added.")
        return node
    else:
        print(f"Entity {name} already exists.")
        return None


def add_relationship(self, name_source, rel_type, name_target):
    from_entity = self.entities.get(name_source)
    to_entity = self.entities.get(name_target)
    if from_entity and to_entity:
        relationship = RelationshipInfo(rel_type, to_entity)
        from_entity.relationships.append(relationship)
        source_node = self.graph.nodes.match(name=name_source).first()
        target_node = self.graph.nodes.match(name=name_target).first()
        if source_node and target_node:
            self.add_relationship_to_graph(source_node, rel_type, target_node)
            print(
                f"Relationship {rel_type} from {name_source} to {name_target} added."
            )
        else:
            print("One or both entities not found in the graph.")
    else:
        print("One or both entities not found.")


def view_entity_details(self, name):
    query = f"MATCH (n {{name: '{name}'}}) RETURN n"
    result = self.graph.run(query).data()
    if result:
        entity = result[0]["n"]
        print(f"Entity: {entity['name']}")
        print(f"Type: {list(entity.labels)[0]}")
        print(f"Description: {entity['description']}")
    else:
        print(f"No entity found with name {name}.")


def search_entities(self, keyword):
    query = f"MATCH (n) WHERE n.name CONTAINS '{keyword}' OR n.description CONTAINS '{keyword}' RETURN n"
    results = self.graph.run(query).data()
    if not results:
        print(f"No entities found with keyword '{keyword}'.")
    else:
        for result in results:
            entity = result["n"]
            print(
                f"Entity: {entity['name']}, Type: {list(entity.labels)[0]}, Description: {entity['description']}"
            )