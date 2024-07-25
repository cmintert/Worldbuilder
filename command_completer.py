import logging
import shlex
from prompt_toolkit.completion import Completer, Completion

# Configure logging to write to a file


class CommandCompleter(Completer):
    def __init__(self, cli):
        self.cli = cli

    def has_unmatched_quotes(self, text):
        result = text.count('"') % 2 != 0 or text.count("'") % 2 != 0
        return result

    def split_input(self, text_before_cursor):
        if self.has_unmatched_quotes(text_before_cursor):
            words = text_before_cursor.split()

        else:
            try:
                words = shlex.split(text_before_cursor)

            except ValueError:
                words = text_before_cursor.split()

        return words

    def is_suggesting_commands(self, words, text_before_cursor):
        result = len(words) == 0 or (
            len(words) == 1 and not text_before_cursor.endswith(" ")
        )

        return result

    def suggest_commands_and_aliases(self, word_before_cursor):

        for command in self.cli.commands:
            if command.startswith(word_before_cursor):

                yield Completion(command, start_position=-len(word_before_cursor))
        for alias in self.cli.aliases:
            if alias.startswith(word_before_cursor):

                yield Completion(alias, start_position=-len(word_before_cursor))

    def is_command_entered(self, words, text_before_cursor):
        result = len(words) == 1 and text_before_cursor.endswith(" ")

        return result

    def is_typing_arguments(self, words):
        result = len(words) >= 1

        return result

    def suggest_command_arguments(self, words, word_before_cursor):
        command_name = words[0]

        if command_name in self.cli.aliases:
            command_name = self.cli.aliases[command_name]

        if command_name in self.cli.commands:
            existing_args = {
                arg.split("=")[0] for arg in words[1:] if arg.startswith("--")
            }

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
                logging.debug(f"Suggesting entity name: {suggestion}")
                yield Completion(suggestion, start_position=-len(word_before_cursor))

    def suggest_relationship_types(self, word_before_cursor):

        for rel_type in self.cli.world.create_rel_type_catalogue():
            if rel_type.lower().startswith(word_before_cursor.lower()):
                suggestion = rel_type.upper().replace(" ", "_")

                yield Completion(suggestion, start_position=-len(word_before_cursor))

    def suggest_entity_types(self, word_before_cursor):

        for entity_type in self.cli.world.create_entity_type_catalogue():
            if entity_type.lower().startswith(word_before_cursor.lower()):
                suggestion = self.quote_if_needed(entity_type)

                yield Completion(suggestion, start_position=-len(word_before_cursor))

    def quote_if_needed(self, value):
        result = f'"{value}"' if " " in value else value

        return result

    def suggest_argument_values(self, arg, word_before_cursor):

        if arg in ["name", "source", "target"]:
            yield from self.suggest_name_of_entity(word_before_cursor)
        elif arg in ["rel_type"]:
            yield from self.suggest_relationship_types(word_before_cursor)
        elif arg in ["entity_type", "type"]:
            yield from self.suggest_entity_types(word_before_cursor)

    def get_completions(self, document, complete_event):

        text_before_cursor = document.text_before_cursor
        command_parts = self.split_input(text_before_cursor.rstrip())
        current_fragment = document.get_word_before_cursor(WORD=True)

        last_complete_command_part = ""
        if command_parts:
            if text_before_cursor.endswith(" "):
                last_complete_command_part = command_parts[-1]
            elif len(command_parts) > 1:
                last_complete_command_part = command_parts[-2]

        logging.info(
            f"Text before cursor: {text_before_cursor}, command parts: {command_parts}, current fragment: {current_fragment}, last complete command part: {last_complete_command_part}"
        )

        if self.has_unmatched_quotes(text_before_cursor):
            # If there are unclosed quotes, don't provide any suggestions
            return

        # Determine the completion context
        if not command_parts or (
            len(command_parts) == 1 and not text_before_cursor.endswith(" ")
        ):
            # Suggesting commands
            logging.info(f"Suggesting commands")
            yield from self.suggest_commands_and_aliases(current_fragment)

        elif last_complete_command_part.startswith("--"):
            # Suggesting values for an argument
            arg = last_complete_command_part.lstrip("--")
            logging.info(f"Suggesting values for argument: {arg}")
            yield from self.suggest_argument_values(arg, current_fragment)

        else:
            # Suggesting arguments
            logging.info(f"Suggesting arguments")
            yield from self.suggest_command_arguments(command_parts, current_fragment)
