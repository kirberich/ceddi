import re
import time
from dataclasses import dataclass
from enum import StrEnum
from itertools import combinations
from typing import final

from pint.errors import DimensionalityError, UndefinedUnitError
from pint.facets.plain import PlainQuantity

from .expression_parser import (
    FUNCTIONS,
    NUMBER_RE,
    OPERATORS,
    SORTED_OPERATORS,
    WORD_RE,
    ExpressionParser,
    ParseError,
    registry,
)


class CacheMatch(StrEnum):
    HIT = "hit"
    MISS = "miss"
    HIT_NONE = "hit_none"


@dataclass(slots=True)
class CachedLine:
    """The note parser caches lines that have been previously evalulated using this class.

    Because variables can change without the line itself changing, the caching has to take into account
    any variable values used for that line.

    A line matches the cache if all variables match, or in a special case, if at least one variable is missing.
    (If a variable is missing, we already know the line will evalulate to None.)
    """

    result: PlainQuantity[float] | None
    used_variable_values: dict[str, PlainQuantity[float]]

    def variables_match(self, variables: dict[str, PlainQuantity[float]]) -> CacheMatch:
        for variable_name in self.used_variable_values:
            if variable_name not in variables:
                return (
                    CacheMatch.HIT_NONE
                )  # If a variable is missing, the value will always be None
            if self.used_variable_values[variable_name] != variables[variable_name]:
                return CacheMatch.MISS
        return CacheMatch.HIT


@final
class NoteParser:
    """A parser that can find and evaluate mathematical expressions embedded in lines of text."""

    cache: dict[str, CachedLine]
    cache_hits: int
    cache_misses: int

    def __init__(self):
        self.expression_parser = ExpressionParser()
        self.cache = {}
        self.cache_hits = 0
        self.cache_misses = 0

        # Build a regex to find all possible tokens
        operator_pattern = "|".join(re.escape(op) for op in SORTED_OPERATORS)
        paren_pattern = r"\(|\)"

        # Operators must be checked before words to correctly handle "to"
        self.token_re = re.compile(
            f"({NUMBER_RE.pattern})|({operator_pattern})|({WORD_RE.pattern})|({paren_pattern})"
        )

    def parse_line(
        self, line: str, variables: dict[str, PlainQuantity[float]]
    ) -> PlainQuantity[float] | None:
        """
        Finds and evaluates the most likely mathematical expression within a line of text,
        even if it is interrupted by other text.
        """

        matches = list(self.token_re.finditer(line))

        # Filter out irrelevant words to reduce the search space
        all_tokens: list[str] = []
        for match in matches:
            # lastindex tells us which capture group in the regex matched.
            # 1: number, 2: operator, 3: word, 4: parenthesis
            if match.groupdict().get("word", None) is not None:
                word = match.group(0)
                if word in FUNCTIONS or word in variables:
                    all_tokens.append(word)
                else:
                    try:
                        registry.Unit(word)
                        all_tokens.append(word)
                    except (UndefinedUnitError, AttributeError):
                        pass
                        # Not a function, variable, or unit, so ignore it.
            else:
                # It's a number, operator, or parenthesis, so keep it.
                all_tokens.append(match.group(0))

        if not all_tokens:
            return None

        if line in self.cache:
            match = self.cache[line].variables_match(variables)

            if match in (CacheMatch.HIT, CacheMatch.HIT_NONE):
                self.cache_hits += 1
                return self.cache[line].result if match == CacheMatch.HIT else None

        before = time.time()
        # Try all possible ordered subsequences of tokens, from longest to shortest
        for length in range(len(all_tokens), 0, -1):
            for subsequence in combinations(all_tokens, length):
                expr_string = " ".join(subsequence)
                try:
                    # We need to ensure that the expression we're trying to parse
                    # is "complete" and doesn't have hanging operators or parens
                    # that would be technically valid but nonsensical.
                    # A simple heuristic is to check if it starts/ends with an operator.
                    if any(expr_string.startswith(op) for op in OPERATORS) or any(
                        expr_string.endswith(op) for op in OPERATORS
                    ):
                        continue

                    result, used_variables = self.expression_parser.parse(
                        expr_string, variables
                    )
                    self.cache[line] = CachedLine(
                        result,
                        {
                            variable_name: variables[variable_name]
                            for variable_name in used_variables
                        },
                    )
                    self.cache_misses += 1

                    if (duration := (time.time() - before)) > 0.1:
                        print(f"Slow parse: {line} ({duration:.2f}s)")

                    return result
                except (ParseError, ValueError, DimensionalityError):
                    continue

        self.cache_misses += 1
        return None
