from typing import Callable
from gi.repository import Gtk

ClickCallback = Callable[[Gtk.Button], None]


class MenuBar:
    on_new_clicked: ClickCallback
    on_folder_selected: ClickCallback

    def __init__(
        self, on_new_clicked: ClickCallback, on_folder_selected: ClickCallback
    ):
        self.on_new_clicked = on_new_clicked
        self.on_folder_selected = on_folder_selected

    def as_widget(self) -> Gtk.Box:
        menu_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        menu_bar.set_margin_top(6)
        menu_bar.set_margin_bottom(6)
        menu_bar.set_margin_start(6)
        menu_bar.set_margin_end(6)

        new_button = Gtk.Button(label="New")
        new_button.connect("clicked", self.on_new_clicked)
        menu_bar.append(new_button)

        open_folder_button = Gtk.Button(label="Open Folder")
        open_folder_button.connect("clicked", self.on_folder_selected)
        menu_bar.append(open_folder_button)

        return menu_bar
