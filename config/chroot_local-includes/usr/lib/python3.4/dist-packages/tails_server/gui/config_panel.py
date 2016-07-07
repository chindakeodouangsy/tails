import collections
import logging
import os
import sh

from gi.repository import Gtk

from tails_server.gui.option_row import OptionRow
from tails_server.gui.service_status import STATUS_STOPPED, STATUS_STOPPING

from tails_server.config import CONFIG_UI_FILE


class ServiceConfigPanel(object):

    def __init__(self, gui, service):
        logging.debug("Instantiating config panel for service %r", service.name)
        self.gui = gui
        self.service = service
        self.builder = Gtk.Builder()
        self.builder.add_from_file(CONFIG_UI_FILE)
        self.builder.connect_signals(self)
        self.switch = self.builder.get_object("switch_service_start_stop")
        self.new_onion_address_button = self.builder.get_object("button_new_onion_address")
        self.onion_address_label = self.builder.get_object("label_onion_address")
        self.connection_string_label = self.builder.get_object("label_connection_string")
        self.onion_address_box = self.builder.get_object("box_onion_address")
        self.connection_string_box = self.builder.get_object("box_connection_string")
        self.options_grid = self.builder.get_object("grid_options")
        self.option_rows = list()
        self.option_groups = set()
        self.group_separators = collections.OrderedDict()
        self.options_populated = False
        if self.service.is_installed:
            self.on_service_installed()

    @property
    def is_active(self):
        return self.gui.current_service == self.service

    def on_service_installed(self):
        self.populate_option_rows()
        self.switch.set_sensitive(True)
        self.show()

    def on_service_removal(self):
        self.remove_option_rows()
        self.switch.set_sensitive(False)

    def populate_option_rows(self):
        if self.options_populated:
            return
        self.options_populated = True
        for widget in (self.onion_address_label,
                       self.connection_string_label,
                       self.onion_address_box,
                       self.connection_string_box):
            widget.set_visible(True)
        self.option_groups = {"connection"} | {
            option.group for option in self.service.options_dict.values() if option.group
            }

        groups = set()
        for option in self.service.options_dict.values():
            if option.group in groups:
                continue
            groups.add(option.group)
            self.add_separator(option.group)
        logging.debug("Option groups: %r", groups)

        for option in self.service.options_dict.values():
            self.add_option(option)

    def remove_option_rows(self):
        for widget in (self.onion_address_label,
                       self.connection_string_label,
                       self.onion_address_box,
                       self.connection_string_box):
            widget.set_visible(False)
        for row in self.option_rows:
            row.box.set_visible(False)
            row.label.set_visible(False)

    def add_separator(self, group):
        logging.debug("Inserting separator for group %r", group)
        # self.group_separators[group] = Gtk.Separator()
        self.group_separators[group] = Gtk.Box()
        if group == "connection":
            self.options_grid.insert_next_to(
                self.onion_address_label,
                Gtk.PositionType.BOTTOM
            )
            self.options_grid.attach_next_to(
                self.group_separators[group],
                self.onion_address_label,
                Gtk.PositionType.BOTTOM,
                width=2, height=1
            )
        else:
            self.options_grid.attach_next_to(
                self.group_separators[group],
                None,
                Gtk.PositionType.BOTTOM,
                width=2, height=1
            )

    def show(self):
        logging.debug("Showing config panel of service %r", self.service)
        icon = self.builder.get_object("image_service_icon")
        _, size = icon.get_icon_name()
        icon.set_from_icon_name(self.service.icon_name, size)

        self.builder.get_object("label_service_name").set_text(self.service.name_in_gui)
        self.builder.get_object("label_service_description").set_text(self.service.description)

        if self.options_populated:
            self.builder.get_object("label_onion_address_value").set_text(str(self.service.address))
            self.builder.get_object("label_connection_string_value").set_text(
                str(self.service.connection_string_in_gui))
            self.set_new_onion_address_button_sensitivity()
            self.set_persistence_sensitivity()
            self.set_autorun_sensitivity()

        config_panel_container = self.gui.builder.get_object("scrolledwindow_service_config")
        for child in config_panel_container.get_children():
            config_panel_container.remove(child)
        config_panel_container.add(self.builder.get_object("viewport_service_config"))
        self.gui.current_service = self.service

    def set_new_onion_address_button_sensitivity(self):
        self.new_onion_address_button.set_sensitive(not self.service.is_running and
                                                    self.service.address is not None)

    def set_persistence_sensitivity(self):
        try:
            persistence_row = [r for r in self.option_rows if r.option.name == "persistence"][0]
        except IndexError:
            logging.warning("No 'persistence' option for service %r", self.service)
            return

        if os.path.exists("/live/persistence/TailsData_unlocked"):
            persistence_row.sensitive = True
            label = self.builder.get_object("label_persistence_comment")
            if label in persistence_row.box.get_children():
                persistence_row.box.remove(label)
            return

        logging.debug("Setting persistence sensitivity to False")
        persistence_row.sensitive = False
        label = self.builder.get_object("label_persistence_comment")
        if label not in persistence_row.box.get_children():
            persistence_row.box.pack_end(label, expand=True, fill=True, padding=0)

    def set_autorun_sensitivity(self):
        try:
            autostart_row = [r for r in self.option_rows if r.option.name == "autostart"][0]
        except IndexError:
            logging.warning("No 'autostart' option for service %r", self.service)
            return
        if not self.service.options_dict["persistence"].value:
            autostart_row.sensitive = False
        else:
            autostart_row.sensitive = True

    def add_option(self, option):
        try:
            option_row = OptionRow.create(self, option)
        except TypeError as e:
            logging.error(e)
            return
        option_row.show()
        self.option_rows.append(option_row)
        # if not option_row.known_option:
        # self.options_grid.insert_row(-1)
        # self.options_grid.attach(option_row.label, -1, -1, 1, 1)
        if option.group:
            self.add_row_to_group(option_row, option.group)
        else:
            self.options_grid.add(option_row.label)
        self.options_grid.attach_next_to(option_row.box, option_row.label,
                                         Gtk.PositionType.RIGHT, width=1, height=1)

    def add_row_to_group(self, option_row, group):
        logging.debug("Inserting option_row %r above separator of group %r",
                      option_row.option.name, group)
        self.options_grid.insert_next_to(
            self.group_separators[group],
            Gtk.PositionType.TOP
        )
        self.options_grid.attach_next_to(
            option_row.label,
            self.group_separators[group],
            Gtk.PositionType.TOP,
            width=1, height=1
        )

    def set_switch_status(self, status):
        # XXX: Use only either set_active or set_status here?
        self.switch.set_active(status)
        self.switch.set_state(status)

    def update_switch_status(self):
        if self.service.status.service_status in [STATUS_STOPPED, STATUS_STOPPING]:
            self.set_switch_status(False)
        else:
            self.set_switch_status(True)

    def apply_options(self):
        logging.debug("Applying options")
        for option_row in self.option_rows:
            logging.debug("Setting option %r to %r", option_row.option.name, option_row.value)
            option_row.option.value = option_row.value

    def on_copy_entry_clicked(self, entry, icon, event):
        entry.select_region(0, -1)
        entry.copy_clipboard()

    def on_switch_service_start_stop_state_set(self, switch, status):
        logging.debug("on_switch_service_start_stop_state_set. status: %r", status)
        self.service.run_threaded_when_idle(self.on_switch_state_set, status)

    def on_switch_state_set(self, status):
        for option_row in self.option_rows:
            option_row.sensitive = not status
        self.set_new_onion_address_button_sensitivity()
        self.set_autorun_sensitivity()

        is_running = self.service.is_running
        logging.debug("is running: %r", is_running)
        if status and not is_running:
            self.apply_options()
            self.service.run_threaded(self.service.enable)
            self.show()
        if not status and is_running:
            self.service.run_threaded(self.service.disable)

    def on_checkbutton_persistence_toggled(self, checkbutton):
        state = checkbutton.get_active()
        if state:
            self.apply_options()
        self.service.options_dict["persistence"].value = state
        self.set_autorun_sensitivity()

    def on_checkbutton_autostart_toggled(self, checkbutton):
        state = checkbutton.get_active()
        self.service.options_dict["autostart"].value = state

    def on_button_copy_connection_string_clicked(self, button):
        text = self.service.connection_info
        self.gui.clipboard.set_text(text, len(text))

    def on_button_new_onion_address_clicked(self, button):
        confirmed = self.gui.obtain_confirmation(
            title="Generate new onion address",
            text="This will irrevocably change this service's onion address. Are you sure you "
                 "want to proceed?",
            ok_label="Generate new address"
        )
        if not confirmed:
            return
        self.service.remove_onion_address()
        self.show()

    def on_button_help_clicked(self, button):
        sh.sudo("-u", "amnesia", "xdg-open", self.service.documentation)