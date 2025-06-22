import datetime

from pint import DimensionalityError
from pint.facets.plain import PlainQuantity
import pytest

from ceddi.expression_parser import ExpressionParser, ParseError, Quantity


@pytest.mark.parametrize(
    "expr, expected_result",
    [
        # Simple arithmetic
        ("1 + 2", Quantity(3)),
        ("5 - 3", Quantity(2)),
        ("4 * 2", Quantity(8)),
        ("10 / 5", Quantity(2.0)),
        # Precedence
        ("2 + 3 * 4", Quantity(14)),
        # Parentheses
        ("(2 + 3) * 4", Quantity(20)),
        # Associativity
        ("8 - 4 - 2", Quantity(2)),
        ("2 ^ 3 ^ 2", Quantity(512)),
        # Functions
        ("sqrt(16)", Quantity(4)),
        ("2 * sqrt(9)", Quantity(6)),
        # Units
        ("10 m + 5 m", Quantity(15, "m")),
        ("100 km / 10 s", Quantity(10, "km/s")),
        ("2 m * 3 m", Quantity(6, "m*m")),
        ("10 m ^ 2", Quantity(100, "m^2.0")),
        # Complex expressions
        ("3 * (4 + 2)", Quantity(18)),
        ("3 * (sin(0) + 1) kg", Quantity(3, "kg")),
        # datetimes
        ("10 s + 5 s", datetime.timedelta(seconds=15)),
        ("10 s - 5 s", datetime.timedelta(seconds=5)),
        ("10 s * 5 s", Quantity(50, "s*s")),
        ("10 s / 5 s", 2.0),
        ("10 s ^ 2", Quantity(100, "s^2.0")),
        # "to" operator
        ("1 m to cm", Quantity(100, "cm")),
        ("1000 g to kg", Quantity(1, "kg")),
        ("1 g + 1 g to kg", Quantity(0.002, "kg")),
        ("1 g + (1 g to kg)", Quantity(2, "g")),
        ("1 g + (1 g to kg) to kg", Quantity(0.002, "kg")),
        ("5 ft + 6 in to cm", Quantity(167.64, "cm")),
        ("50km/h to m/s", Quantity(13.88888888888889, "m/s")),
    ],
)
def test_valid_expression(
    expr: str, expected_result: PlainQuantity[float] | datetime.timedelta
):
    """Test that valid expressions are parsed correctly."""
    parser = ExpressionParser()
    result, _used_variables = parser.parse(expr)

    if isinstance(expected_result, datetime.timedelta):
        assert result.to_timedelta() == expected_result
    else:
        assert result == expected_result


@pytest.mark.parametrize(
    "expr, variables, expected_result",
    [
        ("x + 1", {"x": Quantity(1)}, Quantity(2)),
        ("x * y", {"x": Quantity(2, "m"), "y": Quantity(3, "s")}, Quantity(6, "m*s")),
        ("x + y", {"x": Quantity(5, "m"), "y": Quantity(10, "m")}, Quantity(15, "m")),
    ],
)
def test_valid_expression_with_variables(
    expr: str,
    variables: dict[str, PlainQuantity[float]],
    expected_result: PlainQuantity[float],
):
    """Test that valid expressions with variables are parsed correctly."""
    parser = ExpressionParser()
    result, _used_variables = parser.parse(expr, variables)
    assert result == expected_result


@pytest.mark.parametrize(
    "expr",
    [
        "1 +",
        "(2 + 3",
        "2 + 3)",
        "10 m + 5 kg",
        "sin(2 m)",
        "sqrt(5kg)",
        "10 m 5",
        "1 ++ 2",
        "1 2",
        "x + 1",  # Undefined variable
        "a",  # just a unit
        "kg",  # just a unit
    ],
)
def test_invalid_expression(expr: str):
    """Test that invalid expressions raise a ValueError."""
    parser = ExpressionParser()
    with pytest.raises((ValueError, DimensionalityError, ParseError)):
        parser.parse(expr)
