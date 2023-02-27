# SPDX-License-Identifier: GPL-3.0-or-later
import os

from gi.repository import Adw, Gtk

from graphs import file_io, graphs, plotting_tools


def toggle_darkmode(_shortcut, _theme, _widget, self):
    if Adw.StyleManager.get_default().get_dark():
        self.plot_settings.plot_style = self.preferences.config[
            "plot_style_dark"]
    else:
        self.plot_settings.plot_style = self.preferences.config[
            "plot_style_light"]
    plotting_tools.reload_plot(self)


def enable_data_dependent_buttons(self, enabled):
    win = self.main_window
    dependent_buttons = [
        win.shift_vertically_button,
        win.translate_x_button,
        win.translate_y_button,
        win.multiply_x_button,
        win.multiply_y_button,
        win.smooth_button,
        win.fourier_button,
        win.inverse_fourier_button,
        win.normalize_button,
        win.center_button,
        win.derivative_button,
        win.integral_button,
        win.transform_button,
        win.combine_button,
    ]
    for button in dependent_buttons:
        button.set_sensitive(enabled)


def disable_clipboard_buttons(self):
    win = self.main_window
    win.redo_button.set_sensitive(False)
    win.undo_button.set_sensitive(False)


def on_confirm_discard_response(_dialog, response, self):
    if response == "discard":
        chooser = self.build("dialogs", "open_project")
        chooser.set_transient_for(self.main_window)
        chooser.connect("response", on_open_response, self, True)
        chooser.show()


def on_open_response(dialog, response, self, project, import_settings=None):
    if response == Gtk.ResponseType.ACCEPT:
        if project:
            graphs.open_project(self, dialog.get_files()[0])
        else:
            graphs.open_files(self, dialog.get_files(), import_settings)


def on_save_response(dialog, response, self, project):
    if response == Gtk.ResponseType.ACCEPT:
        path = dialog.get_file().peek_path()
        if project:
            file_io.save_project(
                path,
                self.plot_settings,
                self.datadict,
                self.version)
        else:
            file_io.save_file(self, path)


def export_figure(self):
    dialog = self.build("dialogs", "export_figure")
    dialog.set_transient_for(self.main_window)
    formats = []
    default_format = None
    for i, (name, fmts) in enumerate(
            self.canvas.get_supported_filetypes_grouped().items()):
        file_filter = Gtk.FileFilter()
        file_filter.set_name(name)
        for fmt in fmts:
            file_filter.add_pattern(f"*.{fmt}")
        dialog.add_filter(file_filter)
        formats.append(name)
        if self.canvas.get_default_filetype() in fmts:
            default_format = i
    # Setting the choice doesn"t always work, so make sure the default
    # format is first.
    formats = [formats[default_format], *formats[:default_format],
               *formats[default_format + 1:]]
    dialog.add_choice("format", "File format", formats, formats)
    dialog.set_choice("format", formats[default_format])

    dialog.set_current_name(self.canvas.get_default_filename())
    dialog.connect("response", on_figure_save_response, self)
    dialog.show()


def on_figure_save_response(dialog, response, self):
    file = dialog.get_file()
    fmt = dialog.get_choice("format")
    fmt = self.canvas.get_supported_filetypes_grouped()[fmt][0]
    dialog.destroy()
    if response != Gtk.ResponseType.ACCEPT:
        return
    try:
        self.canvas.figure.savefig(file.get_path(), format=fmt)
    except Exception:
        self.main_window.add_toast("Unable to save Image")


def show_about_window(self):
    developers = [
        "Sjoerd Broekhuijsen <contact@sjoerd.se>",
        "Christoph Kohnen <christoph.kohnen@disroot.org>"
    ]
    about = Adw.AboutWindow(transient_for=self.main_window,
                            application_name=self.name,
                            application_icon=self.appid,
                            website=self.website,
                            developer_name=self.author,
                            issue_url=self.issues,
                            version=self.version,
                            developers=developers,
                            copyright=f"© {self.copyright} {self.author}",
                            license_type="GTK_LICENSE_GPL_3_0")
    path = os.getenv("XDG_DATA_DIRS").split(":")[0]
    with open(os.path.join(
            path + "/graphs/graphs/whats_new"), "r", encoding="utf-8") as file:
        about.set_release_notes(file.read())
    about.present()
