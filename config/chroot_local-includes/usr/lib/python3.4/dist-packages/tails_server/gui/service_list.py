import collections
import logging

from gi.repository import Gtk

from tails_server.config import APP_NAME, SERVICE_LIST_UI_FILE


class ServiceList(object):

    service_row_dict = collections.OrderedDict()

    def __init__(self, gui):
        self.gui = gui
        self.builder = gui.builder
        self.listbox = self.builder.get_object("listbox_service_status")
        self.remove_service_button = self.builder.get_object("toolbutton_remove_service")

    def __len__(self):
        return len(self.service_row_dict)

    def __getitem__(self, item):
        return list(self.service_row_dict.keys())[item]

    def listboxrow_to_service(self, listboxrow):
        for service, service_row in self.service_row_dict.items():
            if service_row.listboxrow == listboxrow:
                return service
        raise KeyError(listboxrow)

    def get_selected_service(self):
        listboxrow = self.listbox.get_selected_row()
        return self.listboxrow_to_service(listboxrow)

    def add_service(self, service):
        logging.debug("Adding service %r to service list", service.name)
        service_list_row = ServiceListRow(service)
        self.service_row_dict[service] = service_list_row
        self.listbox.add(service_list_row.listboxrow)
        self.remove_service_button.set_sensitive(True)

        service.status.guess_status()
        service.config_panel.update_switch_status()
        service.status.make_states_consistent()
        service.activate_status_monitor()

    def remove_service(self, service):
        service_row = self.service_row_dict[service]
        del self.service_row_dict[service]
        self.listbox.remove(service_row.listboxrow)
        if len(self) > 0:
            self.select_service(self[0])
        else:
            self.gui.show_config_panel_placeholder()
            self.remove_service_button.set_sensitive(False)

    def row_selected(self, listboxrow):
        service = self.listboxrow_to_service(listboxrow)
        self.service_selected(service)

    def select_service(self, service):
        self.listbox.select_row(self.service_row_dict[service].listboxrow)
        self.service_selected(service)

    def service_selected(self, service):
        service.config_panel.show()


class ServiceListRow(object):
    def __init__(self, service):
        self.builder = Gtk.Builder()
        self.builder.set_translation_domain(APP_NAME)
        self.builder.add_from_file(SERVICE_LIST_UI_FILE)
        self.listboxrow = self.builder.get_object("listboxrow_service_status")
        label = self.builder.get_object("label_status_title")
        label.set_label(service.name_in_gui)
        icon = self.builder.get_object("image_status_service_icon")
        _, size = icon.get_icon_name()
        icon.set_from_icon_name(service.icon_name, size)
