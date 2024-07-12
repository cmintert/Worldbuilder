import unittest
from unittest.mock import MagicMock, patch
from main import World, DatabaseManager, GraphDatabaseOperations


class TestWorldIntegration(unittest.TestCase):
    def setUp(self):
        # Create a mock DatabaseManager
        self.mock_db_manager = MagicMock(spec=DatabaseManager)

        # Patch the DatabaseManager in the World class
        with patch("main.DatabaseManager", return_value=self.mock_db_manager):
            self.world = World("mock_uri", "mock_user", "mock_password")

        # Create a mock for GraphDatabaseOperations
        self.mock_db_operations = MagicMock(spec=GraphDatabaseOperations)
        self.world.db_operations = self.mock_db_operations

        # Initialize an empty entities dictionary to simulate database state
        self.world.entities = {}

    def test_create_and_query_entity(self):
        # Mock the create_entity method
        mock_entity = {
            "name": "John Doe",
            "entity_type": "Character",
            "description": "A test character",
        }
        self.mock_db_operations.create_entity.return_value = mock_entity

        # Create an entity
        self.world.add_entity("Character", "John Doe", "A test character")

        # Mock the query_entities method
        self.mock_db_operations.query_entities.return_value = [mock_entity]

        # Query for the entity
        entities = self.world.list_entities(type="Character")

        # Assert that the entity was created and can be queried
        self.assertEqual(len(entities), 1)
        self.assertEqual(entities[0]["name"], "John Doe")
        self.assertEqual(entities[0]["entity_type"], "Character")
        self.assertEqual(entities[0]["description"], "A test character")

    def test_create_relationship_and_query(self):
        # Mock entities
        self.world.entities = {"John Doe": MagicMock(), "Test City": MagicMock()}

        # Mock the create_relationship method
        mock_relationship = {"type": "LIVES_IN", "properties": {}}
        self.mock_db_operations.create_relationship.return_value = mock_relationship

        # Create a relationship
        self.world.add_relationship("John Doe", "LIVES_IN", "Test City")

        # Mock the query_relationships method
        mock_query_result = [
            {
                "source": {"name": "John Doe", "entity_type": "Character"},
                "relationship": {"type": "LIVES_IN"},
                "target": {"name": "Test City", "entity_type": "Location"},
            }
        ]
        self.mock_db_operations.query_relationships.return_value = mock_query_result

        # Query for the relationship
        relationships = self.world.list_relationships(
            source_type="Character", rel_type="LIVES_IN"
        )

        # Assert that the relationship was created and can be queried
        self.assertEqual(len(relationships), 1)
        self.assertEqual(relationships[0]["source"]["name"], "John Doe")
        self.assertEqual(relationships[0]["target"]["name"], "Test City")
        self.assertEqual(relationships[0]["relationship"]["type"], "LIVES_IN")

    def test_modify_entity_and_query(self):
        # Mock the initial entity
        self.world.entities["John Doe"] = MagicMock()

        # Mock the update_entity method
        mock_modified_entity = {
            "name": "Jane Doe",
            "entity_type": "Character",
            "description": "Modified description",
        }
        self.mock_db_operations.update_entity.return_value = mock_modified_entity

        # Modify the entity
        self.world.modify_entity(
            "John Doe", new_name="Jane Doe", description="Modified description"
        )

        # Mock the query_entities method
        self.mock_db_operations.query_entities.return_value = [mock_modified_entity]

        # Query for the modified entity
        entities = self.world.list_entities(name="Jane Doe")

        # Assert that the entity was modified and can be queried
        self.assertEqual(len(entities), 1)
        self.assertEqual(entities[0]["name"], "Jane Doe")
        self.assertEqual(entities[0]["description"], "Modified description")


if __name__ == "__main__":
    unittest.main()
