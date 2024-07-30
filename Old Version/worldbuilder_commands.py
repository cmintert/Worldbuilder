def register_commands(cli) -> None:
    cli.register_command(
        "list_entities",
        "List entities in the world",
        cli.world.list_entities,
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

    cli.register_command(
        "list_relationships",
        "List relationships in the world",
        cli.world.list_relationships,
        {
            "source_type": {"help": "Type of source entities"},
            "rel_type": {"help": "Type of relationship"},
            "target_type": {"help": "Type of target entities"},
        },
        aliases=["lr"],
    )

    cli.register_command(
        "add_entity",
        "Adds an entity to the world",
        cli.world.add_entity,
        {
            "entity_type": {
                "help": "Type of entity to add, e.g., Character, Location, Artifact"
            },
            "name": {"help": "Name of the entity to add"},
            "description": {"help": "Description of the entity to add"},
            "properties": {"help": "Additional properties for the entity (optional)"},
        },
        aliases=["ae"],
    )

    cli.register_command(
        "modify_entity",
        "Edits an entity in the world",
        cli.world.modify_entity,
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

    cli.register_command(
        "add_relationship",
        "Adds a relationship between two entities",
        cli.world.add_relationship,
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

    cli.register_command(
        "add_property",
        "Adds a new property to an entity",
        cli.world.add_property,
        {
            "name": {"help": "Name of the entity to add the property to"},
            "property_name": {"help": "Name of the new property"},
            "property_value": {"help": "Value of the new property"},
        },
        aliases=["ap"],
    )

    cli.register_command(
        "modify_property",
        "Modifies an existing property of an entity",
        cli.world.modify_property,
        {
            "name": {"help": "Name of the entity to modify the property of"},
            "property_name": {"help": "Name of the property to modify"},
            "new_value": {"help": "New value for the property"},
        },
        aliases=["mp"],
    )
    cli.register_command(
        "delete_property",
        "Deletes an existing property from an entity",
        cli.world.delete_property,
        {
            "name": {"help": "Name of the entity to delete the property from"},
            "property_name": {"help": "Name of the property to delete"},
        },
        aliases=["dp"],
    )

    cli.register_command(
        "view_entity",
        "Display detailed information about an entity",
        cli.world.get_entity_details,
        {
            "name": {"help": "Name of the entity to view"},
        },
        aliases=["ve"],
    )

    cli.register_command(
        "view_graph",
        "Display a graph of entity relationships",
        cli.world.get_entity_graph,
        {
            "name": {"help": "Name of the entity to start the graph from"},
            "depth": {"help": "Depth of the relationship graph (default: 3, max: 5)"},
        },
        aliases=["vg"],
    )
