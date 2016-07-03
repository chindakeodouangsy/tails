import logging

from gi.repository import Gtk

from tails_server.gui.util import DisableOtherWindows

from tails_server.config import SERVICE_CHOOSER_UI_FILE


class ServiceChooser(object):

    row_to_service_dict = dict()

    def __init__(self, gui):
        self.gui = gui
        self.builder = Gtk.Builder()
        self.builder.add_from_file(SERVICE_CHOOSER_UI_FILE)
        self.builder.connect_signals(self)
        self.listbox = self.builder.get_object("listbox_add_service")
        self.window = self.builder.get_object("service_chooser_dialog")
        self.window.set_transient_for(gui.window)
        self.window.set_title("Add Service")
        self.load_services()
        self.disable_other_windows = DisableOtherWindows(self.window)

    def show(self):
        self.window.show_all()
        self.listbox.unselect_all()
        self.disable_other_windows.disable_other_windows()

    def on_service_chooser_dialog_destroy(self, window):
        logging.debug("on_service_chooser_dialog_destroy")
        self.disable_other_windows.reenable_other_windows()

    def on_listbox_add_service_row_activated(self, window, listboxrow):
        self.row_selected(listboxrow)

    def load_services(self):
        for service in self.gui.services:
            self.add_service(service)

    def add_service(self, service):
        new_builder = Gtk.Builder()
        new_builder.add_from_file(SERVICE_CHOOSER_UI_FILE)
        title_label = new_builder.get_object("label_add_service_title")
        title_label.set_text(service.name_in_gui)
        description_label = new_builder.get_object("label_add_service_description")
        description_label.set_text(service.description)
        icon = new_builder.get_object("image_add_service_icon")
        _, size = icon.get_icon_name()
        icon.set_from_icon_name(service.icon_name, size)
        row = new_builder.get_object("listboxrow_add_service")
        self.row_to_service_dict[row] = service
        if service.is_installed:
            row.set_sensitive(False)
        self.listbox.add(row)

    def row_selected(self, listboxrow):
        service = self.row_to_service_dict[listboxrow]
        self.disable_other_windows.reenable_other_windows()
        self.window.hide()
        self.gui.service_list.add_service(service)
        self.gui.service_list.select_service(service)

        service.run_threaded(service.install)
