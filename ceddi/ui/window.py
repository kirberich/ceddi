from pathlib import Path
from typing import Any

from gi.repository import Gtk

from .editor import Editor, LoadError
from .file_list import FileList
from .results import Results
from .menu_bar import MenuBar


class MainWindow(Gtk.ApplicationWindow):
    """Main application window."""

    editor: Editor
    results: Results
    preview_view: Gtk.TextView
    current_file: Path | None = None
    file_list: FileList

    def __init__(self, path: Path, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.set_title("Ceddi")
        self.set_default_size(800, 600)
        self.set_resizable(True)

        # Create main vertical box to hold menu bar and content
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        menu_bar = MenuBar(
            on_new_clicked=self.on_new_clicked,
            on_folder_selected=self.on_open_folder_clicked,
        )

        vbox.append(menu_bar.as_widget())

        # Create a horizontal paned widget for resizable file list
        main_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        main_paned.set_resize_start_child(False)  # File list doesn't resize by default
        main_paned.set_resize_end_child(True)     # Editor area resizes
        main_paned.set_shrink_start_child(False)  # File list can't shrink below minimum
        main_paned.set_shrink_end_child(False)    # Editor area can't shrink below minimum

        self.file_list = FileList(path, on_select=self.on_file_selected)
        list_view = self.file_list.as_widget()

        file_list_scroll = Gtk.ScrolledWindow(vexpand=True)
        file_list_scroll.set_size_request(200, -1)
        file_list_scroll.set_child(list_view)
        main_paned.set_start_child(file_list_scroll)

        right_scroll = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        main_paned.set_end_child(right_scroll)

        editors = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        self.editor = Editor(on_content_changed=self.on_editor_content_changed)
        editors.append(self.editor.as_widget())

        self.results = Results()
        editors.append(self.results.as_widget())
        right_scroll.set_child(editors)

        vbox.append(main_paned)
        self.set_child(vbox)

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

        print(f"Editor content changed. Length: {len(content)} characters")
        self.results.recalculate(content)

        if not self.current_file:
            return

        with open(self.current_file, "w") as f:
            f.write(content)

    def on_new_clicked(self, _button: Gtk.Button) -> None:
        """When new is clicked, create a new file in the currently selected folder."""
        current_folder = self.file_list.selected_folder()

        conflicting_files = list(current_folder.glob("new_file*.txt"))
        if conflicting_files:
            new_file = current_folder / f"new_file_{len(conflicting_files)}.txt"
        else:
            new_file = current_folder / "new_file.txt"

        new_file.touch(exist_ok=False)

        self.file_list.refresh()
        self.on_file_selected(new_file)

    def on_open_folder_clicked(self, _button: Gtk.Button) -> None:
        """Handle Open Folder button click."""
        dialog = Gtk.FileChooserDialog(
            title="Open Folder",
            action=Gtk.FileChooserAction.SELECT_FOLDER,
        )
        dialog.set_transient_for(self)
        dialog.add_buttons(
            "_Cancel",
            Gtk.ResponseType.CANCEL,
            "_Open",
            Gtk.ResponseType.OK,
        )

        dialog.connect("response", self.on_folder_dialog_response)
        dialog.show()

    def on_folder_dialog_response(
        self, dialog: Gtk.FileChooserDialog, response: int
    ) -> None:
        """Handle folder dialog response."""
        if response == Gtk.ResponseType.OK:
            folder = dialog.get_file()
            if not folder:
                return

            path_name = folder.get_path()
            assert path_name is not None, "Folder path should not be None"

            folder_path_str = Path(path_name)
            self.file_list.set_root_path(folder_path_str)

        dialog.destroy()
