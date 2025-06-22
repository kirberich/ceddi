from pathlib import Path
from typing import Callable

from gi.repository import Gtk, Pango


class LoadError(Exception):
    """An error occurred while loading a file into the editor."""


class Editor:
    """The main editor widget."""

    text_view: Gtk.TextView
    buffer: Gtk.TextBuffer
    _on_content_changed: Callable[[str], None]

    header_tag: Gtk.TextTag
    sum_tag: Gtk.TextTag

    def __init__(self, on_content_changed: Callable[[str], None]):
        """Initialize the editor."""
        self._on_content_changed = on_content_changed

        self.buffer = Gtk.TextBuffer()

        # Create a tag for comments
        self.header_tag = self.buffer.create_tag("header", weight=Pango.Weight.BOLD)
        self.sum_tag = self.buffer.create_tag("sum", underline=Pango.Underline.SINGLE)

        self.text_view = Gtk.TextView(buffer=self.buffer)
        self.text_view.set_hexpand(True)
        self.text_view.set_vexpand(True)

        self.buffer.connect("changed", self._on_buffer_changed)

    def _on_buffer_changed(self, buffer: Gtk.TextBuffer) -> None:
        """Internal handler for buffer changes."""
        self.apply_formatting()

        start, end = buffer.get_bounds()
        content = buffer.get_text(start, end, False)
        self._on_content_changed(content)

    def apply_formatting(self) -> None:
        """Apply syntax highlighting to the buffer."""
        start_iter, end_iter = self.buffer.get_bounds()

        # Remove old tags
        self.buffer.remove_tag_by_name("header", start_iter, end_iter)

        # Apply new tags
        line_start = start_iter.copy()
        while line_start.compare(end_iter) < 0:
            line_end = line_start.copy()
            if not line_end.ends_line():
                line_end.forward_to_line_end()

            line_text = self.buffer.get_text(line_start, line_end, False)
            self.buffer.remove_all_tags(line_start, line_end)

            if line_text.strip().startswith("##"):
                self.buffer.apply_tag(self.header_tag, line_start, line_end)

            if line_text.strip() == "sum":
                self.buffer.apply_tag(self.sum_tag, line_start, line_end)

            # Move to the start of the next line, or break if we're at the end
            if not line_start.forward_line():
                break

    def load_text(self, content: str) -> None:
        """Set the editor content."""
        self.buffer.set_text(content)
        self.apply_formatting()

    def load_file(self, file_path: Path):
        """Load a file into the editor."""
        if not file_path.exists():
            raise LoadError(f"File {file_path} does not exist")
        if not file_path.is_file():
            raise LoadError(f"File {file_path} is not a file")

        try:
            content = file_path.read_text()
            self.load_text(content)
            return True
        except Exception as e:
            raise LoadError(f"Error loading file {file_path}: {e}") from e

    def clear(self) -> None:
        """Clear the editor content."""
        self.load_text("")

    def as_widget(self) -> Gtk.TextView:
        """Get the editor as a GTK widget."""
        return self.text_view
