"""Houdini-style pruning over Frama-C/WP invariant results."""

import logging
import re
from typing import List, Optional, Tuple

from .config import HOUDINI_CONFIG


_INVARIANT_RE = re.compile(
    r"^(\s*)loop\s+invariant\s+([^;]+?);",
    flags=re.MULTILINE,
)


class HoudiniPruner:
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)

    @staticmethod
    def _extract_invariants_from_code(code: str) -> List[str]:
        return [match.group(2).strip() for match in _INVARIANT_RE.finditer(code)]

    def prune_annotations(self, validate_result: List[bool], annotations: str) -> str:
        """Remove invariant lines whose positional WP result is false."""
        matches = list(_INVARIANT_RE.finditer(annotations))
        if len(validate_result) != len(matches):
            self.logger.error(
                "Houdini received %d results for %d invariants",
                len(validate_result),
                len(matches),
            )
            return annotations

        result_iter = iter(validate_result)
        return _INVARIANT_RE.sub(
            lambda match: match.group(0) if next(result_iter) else "",
            annotations,
        )

    def houdini(
        self,
        code: str,
        verifier,
        c_file_path: str,
        record: Optional[dict] = None,
    ) -> Tuple[Optional[str], bool]:
        """Iteratively remove failed invariants until the remaining set verifies."""
        if not code or not code.strip():
            self.logger.error("Houdini received empty code")
            return None, False
        if not re.search(
            r"\b(?:void|int|char|long|short|double|float)\s+\w+\s*\(", code
        ):
            self.logger.error("Houdini received incomplete code (no function definition)")
            return None, False

        current_code = code
        max_iterations = HOUDINI_CONFIG.get("max_iterations", 500)
        for iteration in range(max_iterations):
            with open(c_file_path, "w", encoding="utf-8") as source:
                source.write(current_code)
            verifier.run(c_file_path)
            results = list(verifier.validate_result or [])
            invariants = self._extract_invariants_from_code(current_code)

            if record is not None:
                record.setdefault("rounds", []).append({
                    "invariants": invariants,
                    "validate_result": results,
                })

            if not invariants or len(results) != len(invariants):
                self.logger.error(
                    "Houdini cannot map %d WP results to %d invariants",
                    len(results),
                    len(invariants),
                )
                return None, False
            if all(results):
                self.logger.info(
                    "Houdini iteration %d: all %d invariants are valid",
                    iteration + 1,
                    len(invariants),
                )
                return current_code, True

            next_code = self.prune_annotations(results, current_code)
            remaining = self._extract_invariants_from_code(next_code)
            self.logger.info(
                "Houdini iteration %d: removed %d invariants (%d remain)",
                iteration + 1,
                sum(not result for result in results),
                len(remaining),
            )
            if next_code == current_code or not remaining:
                return None, False
            current_code = next_code

        self.logger.error("Houdini reached the %d-iteration limit", max_iterations)
        return None, False
