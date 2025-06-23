from pathlib import Path
from typing import Any

from gi.repository import Gtk

from .editor import Editor, LoadError
from .file_view import FileList
from .results import Results


class MainWindow(Gtk.ApplicationWindow):
    """Main application window."""

    editor: Editor
    results: Results
    preview_view: Gtk.TextView
    current_file: Path | None = None

    def __init__(self, path: Path, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        # Set up the windowu
        self.set_title("CEDDI GTK4 App")
        self.set_default_size(800, 600)
        self.set_resizable(True)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        file_list = FileList(path, on_select=self.on_file_selected)
        list_view = file_list.as_widget()

        file_list_scroll = Gtk.ScrolledWindow(vexpand=True)
        file_list_scroll.set_size_request(200, -1)
        file_list_scroll.set_child(list_view)
        hbox.append(file_list_scroll)

        right_scroll = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        hbox.append(right_scroll)

        editors = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        # Middle - Editor
        self.editor = Editor(on_content_changed=self.on_editor_content_changed)
        editors.append(self.editor.as_widget())

        # Right side - Non-editable TextView
        self.results = Results()
        editors.append(self.results.as_widget())
        right_scroll.set_child(editors)

        # Set the child of the window
        self.set_child(hbox)

    def on_file_selected(self, selected: Path) -> None:
        """Load the selected file into the editor."""
        print(f"selected {selected}")
        if selected.is_dir():
            self.current_file = None
            self.editor.clear()
            return

        self.current_file = selected
        try:
            self.editor.load_file(selected)
        except LoadError as e:
            self.current_file = None
            self.editor.load_text(f"Error loading file {selected}: {e}")

    def on_editor_content_changed(self, content: str) -> None:
        """Handle editor content changes."""
        if not self.current_file:
            return

        print(f"Editor content changed. Length: {len(content)} characters")
        self.results.recalculate(content)

        with open(self.current_file, "w") as f:
            f.write(content)
