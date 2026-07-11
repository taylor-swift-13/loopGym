"""Frama-C/WP result parser used by Houdini and final verification."""

import argparse
import logging
import os
import re
import subprocess
from typing import Dict, List, Optional, Tuple

from .syntax_checker import SyntaxChecker


class OutputVerifier:
    def __init__(self, logger: Optional[logging.Logger] = None, output: bool = False):
        self.logger = logger or logging.getLogger(__name__)
        self.output = output
        self._reset()

    def _reset(self) -> None:
        self.syntax_error = ""
        self.syntax_correct = False
        self.valid_error_list: List[Tuple[str, str, str]] = []
        self.verify_error_list: List[Tuple[str, str, str]] = []
        self.verify_result: List[bool] = []
        self.validate_result: List[bool] = []
        # Source line -> establishment/preservation results, used by refine feedback.
        self.goal_status_by_line: Dict[int, Dict[str, bool]] = {}

    @staticmethod
    def print_errors(error_list) -> None:
        for description, location, content in error_list:
            print(description.splitlines()[0])
            if location:
                print(location)
            if content:
                print(content)
            print()

    def extract_semantic_error(self, error_message: str) -> Tuple[str, str]:
        match = re.search(r"file\s+([\w/\.\-]+),\s+line\s+(\d+)", error_message)
        if not match:
            description = (error_message.strip().splitlines() or ["Unknown error"])[0]
            return (
                f"Location: {description}",
                "Error line content: (unable to parse file/line from Frama-C output)",
            )

        file_path, line_text = match.groups()
        line_number = int(line_text)
        location = f"Error found in file: {file_path} at line: {line_number}"
        try:
            with open(file_path, encoding="utf-8") as source:
                lines = source.readlines()
        except OSError:
            detail = self._extract_proof_obligation(error_message)
            suffix = f" {detail}" if detail else ""
            return location, f"Error line content: (file not found){suffix}"

        if 1 <= line_number <= len(lines):
            return location, f"Error line content: {lines[line_number - 1].strip()}"
        return location, "Error line content: Line number out of range."

    @staticmethod
    def _extract_proof_obligation(error_message: str) -> str:
        for line in error_message.strip().splitlines():
            stripped = line.strip()
            if stripped.startswith("Prove:"):
                return stripped
            if stripped.startswith("Goal") and any(
                kind in stripped for kind in ("Establishment", "Preservation", "Assertion")
            ):
                return stripped
        return ""

    @staticmethod
    def _parse_goal_info(content: str) -> Tuple[Optional[int], Optional[str]]:
        match = re.search(
            r"Goal\s+(Establishment|Preservation)\s+of\s+Invariant\s+"
            r"\(file\s+.*,\s+line\s+(\d+)\)",
            content,
        )
        if not match:
            match = re.search(
                r"Goal\s+(Establishment|Preservation)\s+of\s+Invariant"
                r"[\s\S]*?line\s+(\d+)",
                content,
            )
        if not match:
            return None, None
        return int(match.group(2)), match.group(1)

    @staticmethod
    def _is_content_valid(content: str) -> bool:
        return "Valid" in content and not any(
            marker in content for marker in ("Unknown", "Timeout", "Failed")
        )

    def check_valid_pairs(self, goals: List[str]) -> List[bool]:
        """Require both establishment and preservation for each source line."""
        status_by_line: Dict[int, Dict[str, bool]] = {}
        for goal in goals:
            line, goal_type = self._parse_goal_info(goal)
            if line is None or goal_type is None:
                continue
            status = status_by_line.setdefault(
                line, {"Establishment": False, "Preservation": False}
            )
            status[goal_type] = self._is_content_valid(goal)

        self.goal_status_by_line = status_by_line
        return [
            status_by_line[line]["Establishment"]
            and status_by_line[line]["Preservation"]
            for line in sorted(status_by_line)
        ]

    def check_verify_target(self, goals: List[str]) -> List[bool]:
        return [self._is_content_valid(goal) for goal in goals]

    @staticmethod
    def filter_goal_assertion(contents: List[str]) -> List[str]:
        """Return non-invariant WP goals (assertions, ensures, and contracts)."""
        invariant_prefixes = (
            "Goal Establishment of Invariant",
            "Goal Preservation of Invariant",
        )
        return [
            item for item in contents
            if item.strip().startswith("Goal ")
            and not item.strip().startswith(invariant_prefixes)
        ]

    @staticmethod
    def filter_invariant(contents: List[str]) -> List[str]:
        prefixes = ("Goal Establishment of Invariant", "Goal Preservation of Invariant")
        return [item for item in contents if item.strip().startswith(prefixes)]

    @staticmethod
    def _invariant_count(file_path: str) -> int:
        try:
            with open(file_path, encoding="utf-8") as source:
                return len(re.findall(r"loop\s+invariant\s+[^;]+;", source.read()))
        except OSError:
            return 0

    def run(self, file_name: Optional[str] = None) -> None:
        self._reset()
        if file_name is None:
            parser = argparse.ArgumentParser(description="Run Frama-C WP on a C file.")
            parser.add_argument("file_name", help="path to the C file to analyze")
            file_name = parser.parse_args().file_name
        file_path = os.path.abspath(file_name)
        invariant_count = self._invariant_count(file_path)

        checker = SyntaxChecker()
        checker.run(file_path)
        if self.output:
            self.logger.info(checker.syntax_msg)
        if checker.syntax_msg != "syntax Correct":
            self.syntax_error = checker.syntax_msg
            self.validate_result = [False] * invariant_count
            return

        self.syntax_correct = True
        command = [
            "frama-c", "-wp", "-wp-print", "-wp-timeout", "30", "-wp-par", "8",
            "-wp-prover", "z3", "-wp-model", "Typed", file_path,
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True)
        except (OSError, subprocess.SubprocessError) as exc:
            stdout = getattr(exc, "stdout", "") or ""
            stderr = getattr(exc, "stderr", "") or ""
            self.syntax_error = f"Frama-C execution error: {stdout}{stderr}".strip()
            self.logger.error(self.syntax_error)
            self.validate_result = [False] * invariant_count
            self.verify_result = [False]
            return

        contents = result.stdout.split("------------------------------------------------------------")
        invariant_goals = self.filter_invariant(contents)
        self.validate_result = self.check_valid_pairs(invariant_goals)
        # Missing/malformed WP goals are failures, never implicit survivors.
        if len(self.validate_result) != invariant_count:
            self.logger.warning(
                "Frama-C returned %d invariant results for %d source invariants",
                len(self.validate_result),
                invariant_count,
            )
            self.validate_result += [False] * (invariant_count - len(self.validate_result))
            self.validate_result = self.validate_result[:invariant_count]

        self.valid_error_list = [
            (goal.strip(), *self.extract_semantic_error(goal))
            for goal in invariant_goals
            if not self._is_content_valid(goal)
        ]
        assertion_goals = self.filter_goal_assertion(contents)
        self.verify_result = self.check_verify_target(assertion_goals)
        self.verify_error_list = [
            (goal.strip(), *self.extract_semantic_error(goal))
            for goal in assertion_goals
            if not self._is_content_valid(goal)
        ]

        if self.output:
            self.logger.info("Validate: %s", self.validate_result)
            self.print_errors(self.valid_error_list)
            self.logger.info("Verify: %s", self.verify_result)
            self.print_errors(self.verify_error_list)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    OutputVerifier(logger=logging.getLogger(), output=True).run()
