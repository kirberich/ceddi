import sys

from gi.repository import Gtk

from .ui.window import MainWindow
from argparse import ArgumentParser
from pathlib import Path


class Application(Gtk.Application):
    def __init__(self, path: Path):
        super().__init__(application_id="com.kirberich.ceddi")

        self.connect("activate", self.on_activate, path.resolve())

    def on_activate(self, app: Gtk.Application, path: Path):
        """Handle application activation."""
        window = MainWindow(application=app, path=path)
        window.present()


def main():
    """Main function to run the application."""
    parser = ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()

    app = Application(args.path)
    return app.run([])


if __name__ == "__main__":
    main()
