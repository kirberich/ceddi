from pathlib import Path
from typing import Callable

from gi.repository import Gio, GObject, Gtk


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

    def __init__(self, root_path: Path, on_select: Callable[[Path], None]):
        self.root_path = root_path
        self._on_select = on_select

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

    def on_row_released(
        self,
        _gesture: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
        list_item: Gtk.ListItem,
    ) -> None:
        """Handler for a click on a row to expand/collapse the parent TreeListRow."""
        row = list_item.get_item()
        assert isinstance(row, Gtk.TreeListRow)

        if row.is_expandable():
            row.set_expanded(not row.get_expanded())

    def setup_item(self, _: Gtk.SignalListItemFactory, list_item: Gtk.ListItem) -> None:
        """Setup the widget to show in the list view.

        Each list item consists of a TreeExpander and a Label. A click gesture
        is also added to the list item to toggle expansion.
        """
        expander = Gtk.TreeExpander.new()
        expander.set_child(Gtk.Label())
        list_item.set_child(expander)

        gesture = Gtk.GestureClick.new()
        gesture.connect("released", self.on_row_released, list_item)
        expander.add_controller(gesture)

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

    def as_widget(self) -> Gtk.ListView:
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.setup_item)
        factory.connect("bind", self.bind_item_data)

        root_nodes = Gio.ListStore.new(FileListEntry)
        tree_list_model = Gtk.TreeListModel.new(
            root_nodes, False, False, self.create_children_for_node
        )

        # Add the root items
        for item in self.root_path.iterdir():
            root_nodes.append(FileListEntry(item))

        selection_model = Gtk.SingleSelection(
            model=tree_list_model, autoselect=False, can_unselect=True
        )
        list_view = Gtk.ListView(factory=factory, model=selection_model)

        selection_model.connect("selection-changed", self.on_select)

        # Start without any files selected
        selection_model.unselect_all()

        return list_view
