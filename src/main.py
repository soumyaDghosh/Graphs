# SPDX-License-Identifier: GPL-3.0-or-later
"""Main application."""
import logging
import sys
from gettext import gettext as _
from inspect import getmembers, isfunction

from gi.repository import Adw, GLib, GObject, Gio

from graphs import (actions, file_io, graphs, migrate, plot_styles,
                    plotting_tools, ui)
from graphs.canvas import Canvas
from graphs.clipboard import DataClipboard, ViewClipboard
from graphs.figure_settings import FigureSettings
from graphs.misc import InteractionMode
from graphs.window import GraphsWindow

from matplotlib import font_manager, pyplot


class GraphsApplication(Adw.Application):
    """The main application singleton class."""
    settings = GObject.Property(type=Gio.Settings)
    version = GObject.Property(type=str, default="")
    name = GObject.Property(type=str, default="")
    website = GObject.Property(type=str, default="")
    issues = GObject.Property(type=str, default="")
    author = GObject.Property(type=str, default="")
    pkgdatadir = GObject.Property(type=str, default="")

    datadict = GObject.Property(type=object)
    figure_settings = GObject.Property(type=FigureSettings)
    clipboard = GObject.Property(type=DataClipboard)
    view_clipboard = GObject.Property(type=ViewClipboard)

    def __init__(self, args):
        """Init the application."""
        settings = Gio.Settings(args[1])
        super().__init__(
            application_id=args[1], flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
            version=args[0], name=args[2], website=args[3], issues=args[4],
            author=args[5], pkgdatadir=args[6], datadict={}, settings=settings,
            figure_settings=FigureSettings.new(settings.get_child("figure")),
        )
        migrate.migrate_config(self)
        font_list = font_manager.findSystemFonts(fontpaths=None, fontext="ttf")
        for font in font_list:
            try:
                font_manager.fontManager.addfont(font)
            except RuntimeError:
                logging.warning(_("Could not load %s"), font)
        self.add_actions()
        self.get_style_manager().connect(
            "notify", ui.on_style_change, None, self)

        self.plot_settings = self.props.figure_settings

    def add_actions(self):
        """Create actions, which are defined in actions.py."""
        new_actions = [
            ("quit", ["<primary>q"]),
            ("about", None),
            ("preferences", ["<primary>p"]),
            ("figure_settings", ["<primary><shift>P"]),
            ("add_data", ["<primary>N"]),
            ("add_equation", ["<primary><alt>N"]),
            ("select_all", ["<primary>A"]),
            ("select_none", ["<primary><shift>A"]),
            ("undo", ["<primary>Z"]),
            ("redo", ["<primary><shift>Z"]),
            ("optimize_limits", ["<primary>L"]),
            ("view_back", ["<alt>Z"]),
            ("view_forward", ["<alt><shift>Z"]),
            ("export_data", ["<primary><shift>E"]),
            ("export_figure", ["<primary>E"]),
            ("plot_styles", ["<primary><alt>P"]),
            ("save_project", ["<primary>S"]),
            ("open_project", ["<primary>O"]),
            ("delete_selected", ["Delete"]),
        ]
        methods = {key: item for key, item
                   in getmembers(globals().copy()["actions"], isfunction)}
        for name, keybinds in new_actions:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", methods[f"{name}_action"], self)
            self.add_action(action)

            if keybinds:
                self.set_accels_for_action(f"app.{name}", keybinds)

        settings = self.settings.get_child("figure")
        for val in ["left-scale", "right-scale", "top-scale", "bottom-scale"]:
            string = "linear" if settings.get_enum(val) == 0 else "log"
            action = Gio.SimpleAction.new_stateful(
                f"change-{val}", GLib.VariantType.new("s"),
                GLib.Variant.new_string(string),
            )
            action.connect("activate", plotting_tools.change_scale, self, val)
            self.add_action(action)

        self.toggle_sidebar = Gio.SimpleAction.new_stateful(
            "toggle_sidebar", None, GLib.Variant.new_boolean(True))
        self.toggle_sidebar.connect("activate", actions.toggle_sidebar, self)
        self.add_action(self.toggle_sidebar)
        self.set_accels_for_action("app.toggle_sidebar", ["F9"])

        self.create_mode_action("mode_pan", ["F1"],
                                InteractionMode.PAN)
        self.create_mode_action("mode_zoom", ["F2"],
                                InteractionMode.ZOOM)
        self.create_mode_action("mode_select", ["F3"],
                                InteractionMode.SELECT)

    def do_activate(self):
        """Called when the application is activated.

        We raise the application"s main window, creating it if
        necessary.
        """
        self.main_window = self.props.active_window
        if not self.main_window:
            self.main_window = GraphsWindow(application=self)
        self.main_window.set_title(self.name)
        if "(Development)" in self.name:
            self.main_window.add_css_class("devel")
        pyplot.rcParams.update(
            file_io.parse_style(plot_styles.get_preferred_style(self)))
        self.canvas = Canvas(self)
        self.props.clipboard = DataClipboard(self)
        self.props.view_clipboard = ViewClipboard(self)
        self.main_window.toast_overlay.set_child(self.canvas)
        ui.set_clipboard_buttons(self)
        ui.enable_data_dependent_buttons(self)
        self.set_mode(None, None, InteractionMode.PAN)
        self.props.figure_settings.connect(
            "notify::use-custom-style", ui.on_figure_style_change, self,
        )
        self.props.figure_settings.connect(
            "notify::custom-style", ui.on_figure_style_change, self,
        )
        self.props.figure_settings.connect(
            "notify", lambda _x, _y: graphs.refresh(self),
        )
        self.main_window.present()

    def set_mode(self, _action, _target, mode):
        """Set the current UI interaction mode (none, pan, zoom or select)."""
        win = self.main_window
        pan_button = win.pan_button
        zoom_button = win.zoom_button
        if mode == InteractionMode.PAN:
            pan_button.set_active(True)
            zoom_button.set_active(False)
            select = False
        elif mode == InteractionMode.ZOOM:
            pan_button.set_active(False)
            zoom_button.set_active(True)
            select = False
        elif mode == InteractionMode.SELECT:
            pan_button.set_active(False)
            zoom_button.set_active(False)
            select = True
        win.select_button.set_active(select)
        self.canvas.highlight.set_active(select)
        self.canvas.highlight.set_visible(select)
        win.cut_button.set_sensitive(select)
        for axis in self.canvas.figure.get_axes():
            axis.set_navigate_mode(mode.name if mode.name != "" else None)
        self.interaction_mode = mode
        self.canvas.draw()

    def on_sidebar_toggle(self, _a, _b):
        visible = self.main_window.sidebar_flap.get_reveal_flap()
        self.toggle_sidebar.change_state(GLib.Variant.new_boolean(visible))

    def create_mode_action(self, name, shortcuts, mode):
        """Create action for mode setting."""
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", self.set_mode, mode)
        self.add_action(action)
        self.set_accels_for_action(f"app.{name}", shortcuts)

    def get_settings(self, child=None):
        return self.props.settings if child is None \
            else self.props.settings.get_child(child)


def main(args):
    """The application"s entry point."""
    app = GraphsApplication(args)

    return app.run(sys.argv)
