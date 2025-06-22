import re
from dataclasses import dataclass

from gi.repository import Gtk
from pint.errors import DimensionalityError
from pint.facets.plain import PlainQuantity

from ceddi.expression_parser import WORD_RE, ParseError, Quantity
from ceddi.note_parser import NoteParser

VARIABLE_RE = re.compile(f"^{WORD_RE.pattern} *= *")
parser = NoteParser()


@dataclass
class ParsedLine:
    rendered_line: str
    expression: PlainQuantity[float] | None = None
    variable_name: str | None = None
    comment: str | None = None


class Results:
    text_view: Gtk.TextView
    buffer: Gtk.TextBuffer

    def __init__(self) -> None:
        """Set up the editor UI components."""
        self.text_view = Gtk.TextView()
        self.text_view.set_editable(False)
        self.text_view.set_size_request(200, -1)
        self.text_view.set_vexpand(True)
        self.text_view.set_cursor_visible(False)

        # Get the buffer and connect to changes
        self.buffer = self.text_view.get_buffer()

    def line_is_header(self, line: str) -> bool:
        """Check if a line is a header."""
        return line.strip().startswith("##")

    def running_sum(
        self, section_results: list[PlainQuantity[float]]
    ) -> PlainQuantity[float] | None:
        """Calculate the running sum of a section."""
        try:
            result = sum(section_results)
            if isinstance(result, float | int):
                result = Quantity(result)
            return result
        except DimensionalityError:
            return None

    def parse_line(
        self,
        line: str,
        running_sum: PlainQuantity[float] | None,
        variables: dict[str, PlainQuantity[float]],
    ) -> ParsedLine:
        """Display a line of text."""
        if line == "sum":
            if running_sum is None:
                return ParsedLine(rendered_line="Invalid sum")
            return ParsedLine(rendered_line=f"{running_sum:g~P}")

        variable_name = None
        comment = None
        rendered_line = ""
        if match := VARIABLE_RE.match(line):
            variable_name, content = match.group("word"), line[match.end(0) :]
        else:
            variable_name = ""
            content = line

        if "#" in content:
            expression, comment = content.split("#", 1)
        else:
            expression = content
        expression = expression.strip()

        if not expression.strip():
            rendered_line = ""

        try:
            cache_misses = parser.cache_misses
            parsed_expression = parser.parse_line(expression, variables=variables)
            if parser.cache_misses > cache_misses:
                print(f"Cache miss on: {expression} ({parser.cache_misses} total)")
        except ParseError as e:
            rendered_line = str(e)
            parsed_expression = None

        if parsed_expression is not None:
            if variable_name:
                rendered_line = f"{variable_name} = {parsed_expression:g~P}"
            else:
                rendered_line = f"{parsed_expression:g~P}"

        return ParsedLine(
            variable_name=variable_name,
            expression=parsed_expression,
            rendered_line=rendered_line,
            comment=comment,
        )

    def recalculate(self, editor_content: str) -> None:
        """Set the editor content."""
        results: list[str] = []
        variables: dict[str, PlainQuantity[float]] = {}

        section_results: list[PlainQuantity[float]] = []
        for line in editor_content.splitlines():
            if self.line_is_header(line):
                results.append("")
                section_results = []
                continue

            running_sum = self.running_sum(section_results)
            if running_sum is not None:
                variables["sum"] = running_sum

            parsed_line = self.parse_line(line, running_sum, variables)

            if parsed_line.expression is not None:
                section_results.append(parsed_line.expression)

            if parsed_line.variable_name and parsed_line.expression is not None:
                variables[parsed_line.variable_name] = parsed_line.expression

            results.append(parsed_line.rendered_line)

        self.buffer.set_text("\n".join(results))

    def clear(self) -> None:
        """Clear the editor content."""
        self.buffer.set_text("")

    def as_widget(self) -> Gtk.TextView:
        """Get the editor as a GTK widget.

        Returns:
            The Gtk.TextView widget that can be added to containers.
        """
        return self.text_view
