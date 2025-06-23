import shutil
from pathlib import Path
from typing import Callable

from gi.repository import Gdk, Gio, GObject, Gtk


class FileListEntry(GObject.GObject):
    """An entry in the file tree, containing the name of the file/folder and its children"""

    path: Path

    def __init__(self, path: Path):
        super(FileListEntry, self).__init__()
        self.path = path

    @property
    def name(self) -> str:
        """Return the name of the file or folder."""
        return self.path.name

    @property
    def children(self) -> list["FileListEntry"]:
        if not self.path.exists() or not self.path.is_dir():
            return []

        return [FileListEntry(child_path) for child_path in self.path.iterdir()]


class FileList:
    root_path: Path
    _on_select: Callable[[Path], None]
    item_factory: Gtk.SignalListItemFactory
    list_view: Gtk.ListView
    root_nodes: Gio.ListStore
    tree_list_model: Gtk.TreeListModel
    selection_model: Gtk.SingleSelection

    def __init__(self, root_path: Path, on_select: Callable[[Path], None]):
        self.root_path = root_path
        self._on_select = on_select

        self.item_factory = Gtk.SignalListItemFactory()
        self.item_factory.connect("setup", self.setup_item)
        self.item_factory.connect("bind", self.bind_item_data)

        self.root_nodes = Gio.ListStore.new(FileListEntry)
        self.tree_list_model = Gtk.TreeListModel.new(
            self.root_nodes, False, False, self.create_children_for_node
        )

        self.selection_model = Gtk.SingleSelection(
            model=self.tree_list_model, autoselect=False, can_unselect=True
        )
        self.selection_model.connect("selection-changed", self.on_select)
        # Start without any files selected
        self.selection_model.unselect_all()

        self.list_view = Gtk.ListView(
            factory=self.item_factory, model=self.selection_model
        )

        # Set up drag and drop
        drop_target = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        drop_target.connect("drop", self._on_drop)
        self.list_view.add_controller(drop_target)

    def selected_folder(self) -> Path:
        """Return the currently selected folder."""
        selected_row = self.selection_model.get_selected_item()
        if selected_row is None:
            return self.root_path

        assert isinstance(selected_row, Gtk.TreeListRow), type(selected_row)

        item = selected_row.get_item()
        assert isinstance(item, FileListEntry)

        if not item.path.is_dir():
            return item.path.parent
        return item.path

    def set_root_path(self, path: Path) -> None:
        """Set a new root path for the file list."""
        self.root_path = path
        self.refresh()

    def on_select(
        self, selection: Gtk.SingleSelection, _position: int, _n_items: int
    ) -> None:
        """Handler for a selection change."""
        selected_row = selection.get_selected_item()
        if selected_row is None:
            return

        assert isinstance(selected_row, Gtk.TreeListRow), type(selected_row)

        item = selected_row.get_item()
        assert isinstance(item, FileListEntry)

        self._on_select(item.path)

    def setup_item(self, _: Gtk.SignalListItemFactory, list_item: Gtk.ListItem) -> None:
        """Setup the widget to show in the list view.

        Each list item consists of a TreeExpander and a Label. A click gesture
        is also added to the list item to toggle expansion.
        """
        expander = Gtk.TreeExpander.new()
        expander.set_child(Gtk.Label())
        list_item.set_child(expander)

        # Set up drag source for dragging files
        drag_source = Gtk.DragSource.new()
        drag_source.set_actions(Gdk.DragAction.COPY)
        drag_source.connect("prepare", self._on_drag_prepare, list_item)
        expander.add_controller(drag_source)

    def bind_item_data(self, _: Gtk.SignalListItemFactory, item: Gtk.ListItem):
        """bind data from the FileListEntry and apply it to the widget."""
        expander = item.get_child()
        assert isinstance(expander, Gtk.TreeExpander)

        label = expander.get_child()
        assert isinstance(label, Gtk.Label), (
            f"Expected a label as the child of the expander, got {type(label)}"
        )

        row = item.get_item()
        assert isinstance(row, Gtk.TreeListRow)

        expander.set_list_row(row)
        obj = row.get_item()
        assert isinstance(obj, FileListEntry)

        label.set_label(obj.name)

    def create_children_for_node(self, item: FileListEntry) -> Gio.ListStore | None:
        if not item.children:
            return None

        store = Gio.ListStore.new(FileListEntry)
        for child in item.children:
            store.append(child)
        return store

    def refresh(self) -> None:
        """Reload the file list."""

        self.root_nodes.remove_all()
        for item in self.root_path.iterdir():
            self.root_nodes.append(FileListEntry(item))

    def _on_drag_prepare(
        self,
        _drag_source: Gtk.DragSource,
        _x: float,
        _y: float,
        list_item: Gtk.ListItem,
    ) -> Gdk.ContentProvider | None:
        """Prepare drag operation for a file."""

        row = list_item.get_item()
        if not isinstance(row, Gtk.TreeListRow):
            return None

        file_entry = row.get_item()
        if not isinstance(file_entry, FileListEntry):
            return None

        gfile = Gio.File.new_for_path(str(file_entry.path))
        file_list = Gdk.FileList.new_from_list([gfile])
        return Gdk.ContentProvider.new_for_value(file_list)

    def _on_drop(
        self, _drop_target: Gtk.DropTarget, value: Gio.File, x: float, y: float
    ) -> bool:
        """Handle file drop event."""
        source_name = value.get_path()
        if not source_name:
            return False
        source_path = Path(source_name)
        source_dir = source_path.parent
        print(f"{source_path=} {source_dir=}")

        # Determine target directory based on drop coordinates
        target_dir = self._get_drop_target_directory(x, y)
        if target_dir is None or target_dir == source_dir:
            return False

        # Copy the file to the target directory
        target_path = target_dir / source_path.name

        # Check for name conflicts
        if target_path.exists():
            self._show_error(
                "Failed to move file",
                f"File {source_path.name} already exists in {target_dir}",
            )
            return False

        try:
            shutil.move(source_path, target_path)
        except OSError as e:
            self._show_error("Failed to move file", str(e))
            return False

        # Refresh the file list to show the new file
        self.refresh()
        return True

    def _get_drop_target_directory(self, x: float, y: float) -> Path | None:
        """Determine the target directory for a drop operation using hit testing."""

        # Pick the widget at the given coordinates
        widget = self.list_view.pick(x, y, Gtk.PickFlags.DEFAULT)
        if widget is None:
            print("no widget")
            return None

        # Walk up the widget hierarchy to find the list item
        current = widget

        # Traverse the widget hierarchy to find the GtkListItemWidge
        while not (isinstance(current, Gtk.TreeExpander)):
            if current is None:
                # Somewhere outside the structure, let's assume the root path
                return self.root_path
            current = current.get_parent()

        list_entry = current.get_item()
        assert isinstance(list_entry, FileListEntry), (
            f"Expected a FileListEntry, got {type(list_entry)}"
        )

        # If it's a directory, use it as target; otherwise use its parent
        if list_entry.path.is_dir():
            return list_entry.path
        return list_entry.path.parent

    def _show_error(self, title: str, message: str) -> None:
        """Show error dialog for file name conflicts."""
        dialog = Gtk.MessageDialog(
            transient_for=None,  # We don't have direct access to parent window
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=title,
            secondary_text=message,
        )

        dialog.connect("response", lambda d, _r: d.destroy())
        dialog.show()

    def as_widget(self) -> Gtk.ListView:
        self.refresh()

        return self.list_view
