import unittest
from unittest.mock import MagicMock, patch
from main import World, Entity, Relationship, GraphDatabaseOperations, DatabaseManager


class TestWorldBuilder(unittest.TestCase):

    def setUp(self):
        # Create a mock DatabaseManager
        self.mock_db_manager = MagicMock(spec=DatabaseManager)

        # Patch the DatabaseManager in the World class
        with patch("main.DatabaseManager", return_value=self.mock_db_manager):
            self.world = World("mock_uri", "mock_user", "mock_password")

        # Replace db_operations with a mock
        self.world.db_operations = MagicMock(spec=GraphDatabaseOperations)

    def test_create_entity(self):
        # Arrange
        mock_entity = {
            "name": "John Doe",
            "entity_type": "Character",
            "description": "A test character",
        }
        self.world.db_operations.create_entity.return_value = mock_entity

        # Act
        result = self.world.add_entity("Character", "John Doe", "A test character")

        # Assert
        self.assertEqual(result, mock_entity)
        self.world.db_operations.create_entity.assert_called_once()

    def test_list_entities(self):
        # Arrange
        mock_entities = [
            {
                "name": "John Doe",
                "entity_type": "Character",
                "description": "A test character",
            },
            {
                "name": "Jane Doe",
                "entity_type": "Character",
                "description": "Another test character",
            },
        ]
        self.world.db_operations.query_entities.return_value = mock_entities

        # Act
        result = self.world.list_entities()

        # Assert
        self.assertEqual(result, mock_entities)
        self.world.db_operations.query_entities.assert_called_once()

    def test_add_relationship(self):
        # Arrange
        mock_relationship = {"type": "LIVES_IN", "properties": {}}
        self.world.db_operations.create_relationship.return_value = mock_relationship

        # Add mock entities to the world
        self.world.entities["John Doe"] = MagicMock(spec=Entity)
        self.world.entities["Test City"] = MagicMock(spec=Entity)

        # Act
        result = self.world.add_relationship("John Doe", "LIVES_IN", "Test City")

        # Assert
        self.assertEqual(result, mock_relationship)
        self.world.db_operations.create_relationship.assert_called_once_with(
            "John Doe", "LIVES_IN", "Test City", None
        )

    def test_list_relationships(self):
        # Arrange
        mock_relationships = [
            {
                "source": {"name": "John Doe", "entity_type": "Character"},
                "relationship": {"type": "LIVES_IN"},
                "target": {"name": "Test City", "entity_type": "Location"},
            }
        ]
        self.world.db_operations.query_relationships.return_value = mock_relationships

        # Act
        result = self.world.list_relationships()

        # Assert
        self.assertEqual(result, mock_relationships)
        self.world.db_operations.query_relationships.assert_called_once()

    def test_modify_entity(self):
        # Arrange
        mock_modified_entity = {
            "name": "Jane Doe",
            "entity_type": "Character",
            "description": "Modified description",
        }
        self.world.db_operations.update_entity.return_value = mock_modified_entity

        # Add a mock entity to the world
        self.world.entities["John Doe"] = MagicMock(spec=Entity)

        # Act
        result = self.world.modify_entity(
            "John Doe", new_name="Jane Doe", description="Modified description"
        )

        # Assert
        self.assertEqual(result, mock_modified_entity)
        self.world.db_operations.update_entity.assert_called_once_with(
            "John Doe", {"name": "Jane Doe", "description": "Modified description"}
        )

    def test_add_property(self):
        # Arrange
        mock_entity = MagicMock(spec=Entity)
        self.world.entities["John Doe"] = mock_entity
        mock_updated_entity = {
            "name": "John Doe",
            "entity_type": "Character",
            "description": "A test character",
            "new_property": "new value",
        }
        self.world.db_operations.update_entity.return_value = mock_updated_entity

        # Act
        result = self.world.add_property("John Doe", "new_property", "new value")

        # Assert
        self.assertEqual(result, mock_updated_entity)
        mock_entity.set_property.assert_called_once_with("new_property", "new value")
        self.world.db_operations.update_entity.assert_called_once_with(
            "John Doe", {"new_property": "new value"}
        )

    def test_modify_property(self):
        # Arrange
        mock_entity = MagicMock(spec=Entity)
        mock_entity.get_all_properties.return_value = {"existing_property": "old value"}
        self.world.entities["John Doe"] = mock_entity
        mock_updated_entity = {
            "name": "John Doe",
            "entity_type": "Character",
            "description": "A test character",
            "existing_property": "new value",
        }
        self.world.db_operations.update_entity.return_value = mock_updated_entity

        # Act
        result = self.world.modify_property(
            "John Doe", "existing_property", "new value"
        )

        # Assert
        self.assertEqual(result, mock_updated_entity)
        mock_entity.set_property.assert_called_once_with(
            "existing_property", "new value"
        )
        self.world.db_operations.update_entity.assert_called_once_with(
            "John Doe", {"existing_property": "new value"}
        )

    def test_delete_property(self):
        # Arrange
        mock_entity = MagicMock(spec=Entity)
        mock_entity.get_all_properties.return_value = {
            "name": "John Doe",
            "entity_type": "Character",
            "description": "A test character",
            "deletable_property": "value",
        }
        self.world.entities["John Doe"] = mock_entity
        mock_updated_entity = {
            "name": "John Doe",
            "entity_type": "Character",
            "description": "A test character",
        }
        self.world.db_operations.update_entity.return_value = mock_updated_entity

        # Act
        result = self.world.delete_property("John Doe", "deletable_property")

        # Assert
        self.assertEqual(result, mock_updated_entity)
        mock_entity.delete_property.assert_called_once_with("deletable_property")
        self.world.db_operations.update_entity.assert_called_once_with(
            "John Doe",
            {
                "name": "John Doe",
                "entity_type": "Character",
                "description": "A test character",
            },
        )

    def test_delete_core_property(self):
        # Arrange
        mock_entity = MagicMock(spec=Entity)
        self.world.entities["John Doe"] = mock_entity

        # Act
        result = self.world.delete_property("John Doe", "name")

        # Assert
        self.assertIsNone(result)
        mock_entity.delete_property.assert_not_called()
        self.world.db_operations.update_entity.assert_not_called()


if __name__ == "__main__":
    unittest.main()
