import logging
import sh
import subprocess
from gi.repository import Gtk, GLib, Gdk

from tails_server import import_services
from tails_server import dbus_status_monitor
from tails_server.gui.service import ServiceDecorator
from tails_server.gui.service_list import ServiceList
from tails_server.gui.service_chooser import ServiceChooserDialog
from tails_server.gui import question_dialog

from tails_server.config import APP_NAME, ICON_DIR, MAIN_UI_FILE, TAILS_USER


service_modules_dict = import_services.service_modules_dict


class TailsServerGUI(object):

    current_service = None

    def on_window1_destroy(self, obj, data=None):
        dbus_status_monitor.stop()
        Gtk.main_quit()

    def on_close_clicked(self, button):
        Gtk.main_quit()

    def on_button_add_service_clicked(self, button):
        ServiceChooserDialog(self).run()

    def on_button_remove_service_clicked(self, button):
        service = self.service_list.get_selected_service()
        answer = self.confirm_remove_service()
        if answer != "yes":
            return
        service.run_threaded(self.uninstall_service, service)

    def uninstall_service(self, service: ServiceDecorator):
        service.run_threaded(GLib.idle_add, service.config_panel.on_service_removal)
        service.uninstall()
        GLib.idle_add(self.reset_service, service)
        GLib.idle_add(self.service_list.remove_service, service)

    def reset_service(self, service: ServiceDecorator):
        i = self.services.index(service)
        new_service = service_modules_dict[service.name].service_class()
        self.services[i] = ServiceDecorator(self, new_service)

    def on_listbox_service_status_row_activated(self, listbox, listboxrow):
        self.service_list.row_selected(listboxrow)

    def obtain_confirmation(self, title, text, ok_label, cancel_label="Cancel", destructive=False):
        try:
            sh.zenity(
                "--question",
                "--default-cancel",
                "--ok-label", ok_label,
                "--cancel-label", cancel_label,
                "--title", title,
                "--text", text,
            )
        except sh.ErrorReturnCode_1:
            return False
        return True

    def confirm_restart_service(self):
        dialog = question_dialog.RestartServiceQuestionDialog(self.window)
        dialog.run()
        return dialog.result

    def confirm_apply_changes(self):
        dialog = question_dialog.ApplyChangesQuestionDialog(self.window)
        dialog.run()
        return dialog.result

    def confirm_remove_service(self):
        dialog = question_dialog.RemoveServiceQuestionDialog(self.window)
        dialog.run()
        return dialog.result

    def __init__(self):
        logging.debug("Initializing GUI")
        self.builder = Gtk.Builder()
        self.builder.set_translation_domain(APP_NAME)
        self.builder.add_from_file(MAIN_UI_FILE)
        self.builder.connect_signals(self)

        self.services = [ServiceDecorator(self, module.service_class())
                         for module in service_modules_dict.values()]

        self.service_list = ServiceList(self)
        self.install_persistent_services()

        logging.debug("Adding installed services to service list")
        for service in [service for service in self.services if service.is_installed]:
            self.service_list.add_service(service)

        icon_theme = Gtk.IconTheme.get_default()
        icon_theme.prepend_search_path(ICON_DIR)

        self.window = self.builder.get_object("window1")
        self.service_list_box = self.builder.get_object("service_list_box")
        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

        self.window.connect("delete-event", Gtk.main_quit)
        self.window.set_title("Tails Server")
        self.window.show_all()

        if self.service_list:
            self.service_list.select_service(self.service_list[0])
        else:
            self.show_config_panel_placeholder()

    def install_persistent_services(self):
        logging.debug("Installing persistent services")
        persistent_services = [service for service in self.services if service.is_persistent]
        for service in [service for service in persistent_services if not service.is_installed]:
            service.install()

    def show_config_panel_placeholder(self):
        self.service_list_box.set_visible(False)
        config_panel_container = self.builder.get_object("scrolledwindow_service_config")
        for child in config_panel_container.get_children():
            config_panel_container.remove(child)
        config_panel_container.add(self.builder.get_object("viewport_service_config_placeholder"))

    def on_placeholder_add_service_button_clicked(self, button, data=None):
        response = ServiceChooserDialog(self).run()
        if response == "install":
            self.service_list_box.set_visible(True)

    def on_placeholder_label_activate_link(self, label, uri):
        logging.debug("Opening documentation")
        subprocess.Popen(["sudo", "-u", TAILS_USER, "xdg-open", uri])
        return True

    def disable_main_window(self):
        self.window.set_sensitive(False)

    def enable_main_window(self):
        self.window.set_sensitive(True)