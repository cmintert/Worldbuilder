from __future__ import annotations

import logging
import shlex

from prompt_toolkit.completion import Completer, Completion


class CommandCompleter(Completer):
    def __init__(self, cli):
        self.cli = cli

    def has_unmatched_quotes(self, text):
        # Check if there are unmatched quotes in the text
        return text.count('"') % 2 != 0 or text.count("'") % 2 != 0

    def split_input(self, text_before_cursor):
        if self.has_unmatched_quotes(text_before_cursor):
            words = text_before_cursor.split()
            logging.debug(f"Detected unmatched quotes, words: {words}")
        else:
            try:
                words = shlex.split(text_before_cursor)
                logging.debug(f"Using shlex.split, words: {words}")
            except ValueError:
                words = text_before_cursor.split()
                logging.debug(f"Fallback to simple split, words: {words}")
        return words

    def is_suggesting_commands(self, words, text_before_cursor):
        return len(words) == 0 or (
            len(words) == 1 and not text_before_cursor.endswith(" ")
        )

    def suggest_commands_and_aliases(self, word_before_cursor):
        logging.debug("Suggesting commands and aliases")
        for command in self.cli.commands:
            if command.startswith(word_before_cursor):
                logging.debug(f"Suggesting command: {command}")
                yield Completion(command, start_position=-len(word_before_cursor))
        for alias in self.cli.aliases:
            if alias.startswith(word_before_cursor):
                logging.debug(f"Suggesting alias: {alias}")
                yield Completion(alias, start_position=-len(word_before_cursor))

    def is_command_entered(self, words, text_before_cursor):
        return len(words) == 1 and text_before_cursor.endswith(" ")

    def is_typing_arguments(self, words):
        return len(words) >= 1

    def suggest_command_arguments(self, words, word_before_cursor):
        command_name = words[0]

        if command_name in self.cli.aliases:
            command_name = self.cli.aliases[command_name]

        if command_name in self.cli.commands:

            existing_args = {
                arg.split("=")[0] for arg in words[1:] if arg.startswith("--")
            }
            if not word_before_cursor.startswith("--") and any(
                word.startswith("--") for word in words
            ):
                # If the word before the cursor is not an argument and any word in the input is an argument,
                # it means we are typing the value of an argument, so do not suggest new arguments.
                return
            for arg in self.cli.commands[command_name].arguments:
                if (
                    f"--{arg}".startswith(word_before_cursor)
                    and f"--{arg}" not in existing_args
                ):
                    yield Completion(
                        f"--{arg}", start_position=-len(word_before_cursor)
                    )

    def suggest_name_of_entity(self, word_before_cursor):
        for entity_name in self.cli.world.create_entity_name_catalogue():
            if entity_name.lower().startswith(word_before_cursor.lower()):
                suggestion = self.quote_if_needed(entity_name)
                yield Completion(suggestion, start_position=-len(word_before_cursor))

    def suggest_relationship_types(self, word_before_cursor):
        for rel_type in self.cli.world.create_rel_type_catalogue():
            if rel_type.lower().startswith(word_before_cursor.lower()):
                # suggestion needs to be upper case and blanks replaced by underscores
                suggestion = rel_type.upper().replace(" ", "_")
                yield Completion(suggestion, start_position=-len(word_before_cursor))

    def suggest_entity_types(self, word_before_cursor):
        for entity_type in self.cli.world.create_entity_type_catalogue():
            if entity_type.lower().startswith(word_before_cursor.lower()):
                suggestion = self.quote_if_needed(entity_type)
                yield Completion(suggestion, start_position=-len(word_before_cursor))

    def quote_if_needed(self, value):
        if " " in value:
            return f'"{value}"'
        return value

    def suggest_argument_values(self, arg, word_before_cursor):
        if arg in ["name", "source", "target"]:
            yield from self.suggest_name_of_entity(word_before_cursor)
        elif arg in ["rel_type"]:
            yield from self.suggest_relationship_types(word_before_cursor)
        elif arg in ["entity_type", "type"]:
            yield from self.suggest_entity_types(word_before_cursor)
