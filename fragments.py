# Add the following method to the CommandCompleter class
# This method will collect all available types existing in the database for relationships


def suggest_relationship_types(self, word_before_cursor):
    logging.debug("Suggesting relationship types")
    for rel_type in self.cli.world.get_relationship_types():
        if rel_type.startswith(word_before_cursor):
            logging.debug(f"Suggesting relationship type: {rel_type}")


# Add the following method to the CommandCompleter class
# This method will collect all available types existing in the database for entities


def suggest_entity_types(self, word_before_cursor):
    logging.debug("Suggesting entity types")
    for entity_type in self.cli.world.get_entity_types():
        if entity_type.startswith(word_before_cursor):
            logging.debug(f"Suggesting entity type: {entity_type}")
            yield Completion(entity_type, start_position=-len(word_before_cursor))


# Add the following method to the CommandCompleter class
# This method will collect all available names existing in the database for entities


def suggest_entity_names(self, word_before_cursor):
    logging.debug("Suggesting entity names")
    for entity_name in self.cli.world.get_entity_names():
        if entity_name.startswith(word_before_cursor):
            logging.debug(f"Suggesting entity name: {entity_name}")
            yield Completion(entity_name, start_position=-len(word_before_cursor))
