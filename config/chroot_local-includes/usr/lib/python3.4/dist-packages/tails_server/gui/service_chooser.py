import logging

from tails_server import _
from gi.repository import Gtk

from tails_server.config import APP_NAME, SERVICE_CHOOSER_UI_FILE


class ServiceChooserDialog(object):

    row_to_service_dict = dict()
    selected_row = None

    def __init__(self, gui):
        self.response = None
        self.gui = gui
        self.builder = Gtk.Builder()
        self.builder.set_translation_domain(APP_NAME)
        self.builder.add_from_file(SERVICE_CHOOSER_UI_FILE)
        self.builder.connect_signals(self)
        self.listbox = self.builder.get_object("listbox_add_service")
        self.listbox.set_header_func(self.add_listboxrow_header)
        self.button_install = Gtk.Button()
        self.dialog = self.builder.get_object("service_chooser_dialog")
        self.dialog.set_titlebar(self.build_headerbar())
        self.dialog.set_transient_for(gui.window)
        self.dialog.set_title("Add Service")
        self.load_services()

    def build_headerbar(self):
        headerbar = Gtk.HeaderBar()
        headerbar_sizegroup = Gtk.SizeGroup(Gtk.SizeGroupMode.HORIZONTAL)

        button_cancel = Gtk.Button()
        button_cancel.set_label(_("Cancel"))
        button_cancel.connect('clicked', self.on_button_cancel_clicked)
        headerbar_sizegroup.add_widget(button_cancel)
        headerbar.pack_start(button_cancel)

        self.button_install.set_sensitive(False)
        self.button_install.set_label(_("Install"))
        self.button_install.connect('clicked', self.on_button_install_clicked)
        Gtk.StyleContext.add_class(self.button_install.get_style_context(),
                                   'suggested-action')
        headerbar_sizegroup.add_widget(self.button_install)
        headerbar.pack_end(self.button_install)

        headerbar.show_all()

        return headerbar

    def add_listboxrow_header(self, row, before, data=None):
        if not before:
            return
        separator = Gtk.Separator.new(Gtk.Orientation.HORIZONTAL)
        separator.show()
        row.set_header(separator)

    def run(self):
        self.dialog.run()
        return self.response

    def on_button_cancel_clicked(self, widget, data=None):
        self.response = "cancel"
        self.dialog.hide()

    def on_button_install_clicked(self, widget, data=None):
        self.response = "install"
        self.dialog.hide()
        self.install_selected_service()

    def on_service_chooser_dialog_show(self, widget, data=None):
        self.listbox.unselect_all()

    def on_service_chooser_dialog_delete_event(self, widget, data=None):
        self.dialog.hide()

    def on_listbox_add_service_row_activated(self, window, listboxrow):
        self.selected_row = listboxrow
        self.button_install.set_sensitive(True)

    def load_services(self):
        for service in self.gui.services:
            self.add_service(service)
        self.listbox.show_all()

    def add_service(self, service):
        new_builder = Gtk.Builder()
        new_builder.set_translation_domain(APP_NAME)
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

    def install_selected_service(self):
        service = self.row_to_service_dict[self.selected_row]
        self.gui.service_list.add_service(service)
        self.gui.service_list.select_service(service)
        service.run_threaded(service.install)
