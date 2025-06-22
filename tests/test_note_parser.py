import pytest
from pint.facets.plain import PlainQuantity

from ceddi.expression_parser import Quantity
from ceddi.note_parser import NoteParser


@pytest.mark.parametrize(
    "line, variables, expected_result",
    [
        ("what is 1 + 1", {"x": Quantity(1)}, Quantity(2)),
        (
            "x * y is my favourite number",
            {"x": Quantity(2, "m"), "y": Quantity(3, "s")},
            Quantity(6, "m*s"),
        ),
        ("The angle of the sun is 45 degrees", {}, Quantity(45, "deg")),
        ("A simple calculation: 100 km / 10 s", {}, Quantity(10, "km/s")),
        ("no maths here", {}, None),
        ("2 plus 3", {}, Quantity(2)),  # "plus" is not a known operator
        ("The result is 5m", {}, Quantity(5, "m")),
        ("calculate 1g + (1g to kg)", {}, Quantity(2, "g")),
        ("1kg + 1kg to g", {}, Quantity(2000, "g")),
        ("5 people + 10 bananas", {}, Quantity(15)),
        ("1 (and i mean this) + 1", {}, Quantity(2)),
        ("5+5 from previous results + 10", {}, Quantity(20)),
    ],
)
def test_mixed_expressions(
    line: str,
    variables: dict[str, PlainQuantity[float]],
    expected_result: PlainQuantity[float],
):
    """Test that expressions are correctly extracted and evaluated from mixed text."""
    assert NoteParser().parse_line(line, variables) == expected_result
