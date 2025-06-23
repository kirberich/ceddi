"""Parser for mathematical expressions, using the shunting-yard algorithm

The parser understands basic mathematical expressions (addition, subtraction, multiplication, division, exponentiation, parentheses, trigonometry etc).
It also understands scientific units and currency symbols - all of these are just interpreted as strings by the parser, a separate step converts the results into actual quantities.

Each part of the equation is returned as a Quantity object.

"""

import math
import re
from dataclasses import dataclass
from typing import cast, final

from pint import UnitRegistry
from pint.errors import DimensionalityError, UndefinedUnitError
from pint.facets.plain import PlainQuantity

# Regular expression for a "word" - may be a function or a unit
WORD_RE = re.compile(r"(?P<word>[a-zA-Z_]+[a-zA-Z0-9_]*)")

# regular expression for a number, which may be an integer, float or in scientific notation
NUMBER_RE = re.compile(r"(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?")

OPERATORS = {
    "to": {"precedence": 1, "assoc": "L"},
    "+": {"precedence": 2, "assoc": "L"},
    "-": {"precedence": 2, "assoc": "L"},
    "*": {"precedence": 3, "assoc": "L"},
    "/": {"precedence": 3, "assoc": "L"},
    "^": {"precedence": 4, "assoc": "R"},
}

# A pre-sorted list of operators, longest first, to ensure correct tokenizing
SORTED_OPERATORS = sorted(OPERATORS.keys(), key=len, reverse=True)


FUNCTIONS = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "sqrt": math.sqrt,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "abs": abs,
}

registry = UnitRegistry()
Quantity = registry.Quantity
Unit = registry.Unit


@dataclass(slots=True)
class Number:
    value: float


@dataclass(slots=True)
class Operator:
    op: str
    precedence: int
    assoc: str


@dataclass(slots=True)
class Function:
    name: str


@dataclass(slots=True)
class LeftParen:
    pass


@dataclass(slots=True)
class RightParen:
    pass


Token = (
    Number | Operator | Function | LeftParen | RightParen | str | PlainQuantity[float]
)


class ParseError(Exception):
    """An error occurred while parsing an expression."""


@final
class ExpressionParser:
    """A parser for mathematical expressions, using the shunting-yard algorithm."""

    def _next_token(
        self, expression: str, variables: dict[str, PlainQuantity[float]]
    ) -> tuple[Token | None, int]:
        """Returns the next token in the expression, along with the new offset in the expression."""
        if (char := expression[0]).isspace():
            return None, 1

        # Check for a number first
        if match := NUMBER_RE.match(expression):
            return Number(float(match.group(0))), match.end(0)

        # Check for operators
        for op_str in SORTED_OPERATORS:
            if expression.startswith(op_str):
                op_info = OPERATORS[op_str]
                return Operator(
                    op=op_str,
                    precedence=cast(int, op_info["precedence"]),
                    assoc=cast(str, op_info["assoc"]),
                ), len(op_str)

        # Check for words (functions, variables, units)
        if match := WORD_RE.match(expression):
            word = match.group(0)
            if word in FUNCTIONS:
                return Function(word), match.end(0)
            elif word in variables:
                return variables[word], match.end(0)
            else:
                return word, match.end(0)

        # Check for parentheses
        if char == "(":
            return LeftParen(), 1
        elif char == ")":
            return RightParen(), 1
        else:
            raise ParseError(f"Unknown token in {expression}")

    def _tokenize(
        self, expression: str, variables: dict[str, PlainQuantity[float]]
    ) -> tuple[list[Token], set[str]]:
        """Tokenizes an expression into a list of tokens."""
        tokens: list[Token] = []
        used_variables: set[str] = set()
        remainder = expression
        while remainder:
            token, length = self._next_token(remainder, variables)
            if token is not None:
                tokens.append(token)
            remainder = remainder[length:]

        return tokens, used_variables

    def _apply_operator(
        self, op: Operator, a: PlainQuantity[float], b: PlainQuantity[float]
    ) -> PlainQuantity[float]:
        """Applies an operator to two quantities."""
        if op.op == "to":
            result = a.to(b)
        elif op.op == "+":
            result = a + b
        elif op.op == "-":
            result = a - b
        elif op.op == "*":
            result = a * b
        elif op.op == "/":
            result = a / b
        elif op.op == "^":
            result = a**b
        else:
            raise ParseError(f"Unknown operator: {op.op}")

        assert isinstance(result, Quantity)
        return result

    def _evaluate(self, rpn_queue: list[Token | str | Quantity]) -> Quantity:
        stack: list[PlainQuantity[float]] = []

        for token in rpn_queue:
            if isinstance(token, (Number, Quantity)):
                if isinstance(token, Number):
                    stack.append(Quantity(token.value, registry.Unit("dimensionless")))
                else:
                    stack.append(token)
            elif isinstance(token, str):  # This is a unit or an undefined variable
                try:
                    unit = registry.Unit(token)

                    if not stack:
                        raise ParseError(f"Unit '{token}' has no magnitude.")

                    if isinstance(stack[-1], Quantity) and stack[-1].dimensionless:
                        # This unit is being applied to a dimensionless number, e.g. "10 km"
                        stack[-1] = Quantity(stack[-1].magnitude, unit)
                    else:
                        # This could be part of a compound unit (e.g., the 's' in 'km/s'),
                        # or it could be an argument to 'to'.
                        stack.append(Quantity(1.0, unit))

                except UndefinedUnitError:
                    raise ParseError(f"Unknown unit or variable: {token}")
            elif isinstance(token, Operator):
                if len(stack) < 2:
                    raise ParseError(f"Not enough arguments for operator {token.op}")
                right = stack.pop()
                left = stack.pop()
                try:
                    stack.append(self._apply_operator(token, left, right))
                except DimensionalityError:
                    raise ParseError(f"Incompatible units for operator {token.op}")
            elif isinstance(token, Function):
                if not stack:
                    raise ParseError(f"Not enough arguments for function {token.name}")
                arg = stack.pop()
                if not arg.dimensionless:
                    raise ParseError(
                        f"Cannot apply function {token.name} to a quantity with units"
                    )
                result_mag = FUNCTIONS[token.name](arg.magnitude)
                stack.append(Quantity(result_mag, "dimensionless"))

        if len(stack) != 1:
            raise ParseError("Invalid expression")
        return cast("Quantity", stack[0])

    def parse(
        self, expression: str, variables: dict[str, PlainQuantity[float]] | None = None
    ) -> tuple[Quantity, set[str]]:
        """
        Parses a mathematical expression string into a quantity.

        This method implements Dijkstra's shunting-yard algorithm to convert
        the infix expression string into a postfix (Reverse Polish Notation)
        queue, which is then evaluated by the _evaluate method.
        """
        variables = variables if variables is not None else {}
        tokens, used_variables = self._tokenize(expression, variables)

        # The output_queue will hold the expression in RPN.
        output_queue: list[Token | str | Quantity] = []
        # The operator_stack is for handling operators, functions, and parentheses.
        operator_stack: list[Token] = []

        for token in tokens:
            if isinstance(token, (Number, Quantity)):
                output_queue.append(token)
            elif isinstance(token, str):  # This is a unit or an undefined variable
                # Units are added to the output queue and will be handled during evaluation.
                output_queue.append(token)
            elif isinstance(token, Function):
                # If the token is a function, push it onto the operator stack.
                operator_stack.append(token)
            elif isinstance(token, Operator):
                while (
                    operator_stack
                    and (top := operator_stack[-1])
                    and isinstance(top, Operator)
                    and (
                        (top.assoc == "L" and token.precedence <= top.precedence)
                        or (top.assoc == "R" and token.precedence < top.precedence)
                    )
                ):
                    output_queue.append(operator_stack.pop())
                operator_stack.append(token)
            elif isinstance(token, LeftParen):
                operator_stack.append(token)
            elif isinstance(token, RightParen):
                while operator_stack and not isinstance(operator_stack[-1], LeftParen):
                    output_queue.append(operator_stack.pop())

                # If the stack runs out without finding a left parenthesis, there are mismatched parentheses.
                if not operator_stack or not isinstance(
                    operator_stack.pop(), LeftParen
                ):
                    raise ParseError("Mismatched parentheses")

                # If a function is at the top of the stack, it means the parenthesis
                # was for a function call, so pop the function to the output queue.
                if operator_stack and isinstance(operator_stack[-1], Function):
                    output_queue.append(operator_stack.pop())

        # After iterating through all tokens, pop any remaining operators from the stack to the output queue.
        while operator_stack:
            op = operator_stack.pop()
            # If a left parenthesis is found here, it implies mismatched parentheses.
            if isinstance(op, LeftParen):
                raise ParseError("Mismatched parentheses")
            output_queue.append(op)

        return self._evaluate(output_queue), used_variables
