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

    def get_completions(self, document, complete_event):
        word_before_cursor = document.get_word_before_cursor(WORD=True)
        text_before_cursor = document.text_before_cursor

        words = self.split_input(text_before_cursor)
        if self.is_suggesting_commands(words, text_before_cursor):
            yield from self.suggest_commands_and_aliases(word_before_cursor)
        elif self.is_command_entered(words, text_before_cursor):
            return
        elif self.is_typing_arguments(words):
            yield from self.suggest_command_arguments(words, word_before_cursor)

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

