import collections
import logging
import os
import sh

from gi.repository import Gtk

from tails_server.gui.option_row import OptionRow, ClickableLabel
from tails_server.gui.service_status import Status

from tails_server.config import APP_NAME, CONFIG_UI_FILE, CONNECTION_INFO_UI_FILE


class ServiceConfigPanel(object):

    def __init__(self, gui, service):
        logging.debug("Instantiating config panel for service %r", service.name)
        self.gui = gui
        self.service = service
        self.builder = Gtk.Builder()
        self.builder.set_translation_domain(APP_NAME)
        self.builder.add_from_file(CONFIG_UI_FILE)
        self.builder.connect_signals(self)
        self.switch = self.builder.get_object("switch_service_start_stop")
        self.onion_address_label = self.builder.get_object("label_onion_address")
        self.onion_address_box = self.builder.get_object("box_onion_address")
        onion_address_button = self.builder.get_object("button_onion_address")
        onion_address_button_box = self.builder.get_object("box_button_onion_address")
        onion_address_refresh_image = self.builder.get_object("image_refresh")
        onion_address_value_label = self.builder.get_object("label_onion_address_value")
        self.onion_address_clickable_label = ClickableLabel(
            self.onion_address_box,
            onion_address_button,
            onion_address_button_box,
            onion_address_value_label,
            onion_address_refresh_image
        )
        self.onion_address_clickable_label.clickable = False
        # self.connection_info_label = self.builder.get_object("label_connection_info")
        self.connection_info_box = self.builder.get_object("box_connection_info")
        self.connection_info_button = self.builder.get_object("button_connection_info")
        self.editing_buttonbox = self.builder.get_object("buttonbox_editing")
        self.edit_button = self.builder.get_object("button_edit")
        self.cancel_edit_button = self.builder.get_object("button_cancel_edit")
        self.apply_button = self.builder.get_object("button_apply")
        self.options_grid = self.builder.get_object("grid_options")
        self.option_rows = list()
        self.option_groups = set()
        self.group_separators = collections.OrderedDict()
        self.options_populated = False
        self.in_edit_mode = False
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
                       # self.connection_info_label,
                       self.onion_address_box,
                       self.connection_info_box):
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
            logging.debug("Adding option %r (value: %r)", option.name, option.value)
            self.add_option(option)

    def remove_option_rows(self):
        for widget in (self.onion_address_label,
                       # self.connection_info_label,
                       self.onion_address_box,
                       self.connection_info_box):
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
            self.update_onion_address_widget()
            self.set_connection_info_sensitivity()
            self.update_persistence_checkbox()
            self.update_autorun_checkbox()

        config_panel_container = self.gui.builder.get_object("scrolledwindow_service_config")
        for child in config_panel_container.get_children():
            config_panel_container.remove(child)
        config_panel_container.add(self.builder.get_object("viewport_service_config"))
        self.gui.current_service = self.service

    def update_onion_address_widget(self):
        if self.service.address:
            self.onion_address_box.set_visible(True)
            self.onion_address_label.set_visible(True)
        else:
            self.onion_address_box.set_visible(False)
            self.onion_address_label.set_visible(False)

    def set_connection_info_sensitivity(self):
        if self.service.address:
            self.connection_info_button.set_sensitive(True)
            # self.connection_info_label.set_visible(True)
        else:
            self.connection_info_button.set_sensitive(False)
            # self.connection_info_label.set_visible(False)

    def update_persistence_checkbox(self):
        try:
            persistence_row = [r for r in self.option_rows if r.option.name == "persistence"][0]
        except IndexError:
            logging.warning("No 'persistence' option for service %r", self.service)
            return

        if not self.in_edit_mode:
            persistence_row.sensitive = False
            return

        persistence_row.sensitive = True
        label = self.builder.get_object("label_persistence_comment")
        if label in persistence_row.box.get_children():
            persistence_row.box.remove(label)

    def update_autorun_checkbox(self):
        try:
            autostart_row = [r for r in self.option_rows if r.option.name == "autostart"][0]
        except IndexError:
            logging.warning("No 'autostart' option for service %r", self.service)
            return

        try:
            persistence_row = [r for r in self.option_rows if r.option.name == "persistence"][0]
        except IndexError:
            logging.warning("No 'persistence' option for service %r", self.service)
            return

        if not self.in_edit_mode:
            autostart_row.sensitive = False
            return

        if not persistence_row.value:
            autostart_row.sensitive = False
            autostart_row.value_widget.set_active(False)
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
        logging.debug("Setting switch status to %r", status)
        # XXX: Use only either set_active or set_status here?
        self.switch.set_active(status)
        self.switch.set_state(status)

    def update_switch_status(self):
        if self.service.status.service_status in [Status.stopped, Status.stopping]:
            self.set_switch_status(False)
        else:
            self.set_switch_status(True)

    def apply_options(self):
        logging.debug("Applying options")
        for option_row in self.option_rows:
            logging.debug("Setting option %r to %r", option_row.option.name, option_row.value)
            option_row.option.value = option_row.value

    def apply_options_with_restarting(self):
        self.service.disable()
        self.apply_options()
        self.service.run_threaded(self.service.enable)

    def get_changes(self):
        changes = collections.OrderedDict()
        for option_row in self.option_rows:
            change = option_row.get_change()
            if change:
                changes[option_row.option.name_in_gui] = change
        return changes

    def enter_edit_mode(self):
        if self.in_edit_mode:
            return
        self.in_edit_mode = True
        for option_row in self.option_rows:
            option_row.start_editing()
        self.onion_address_clickable_label.clickable = True
        self.update_persistence_checkbox()
        self.update_autorun_checkbox()
        self.editing_buttonbox.remove(self.edit_button)
        self.editing_buttonbox.pack_start(self.cancel_edit_button, expand=True, fill=True,
                                          padding=0)
        self.editing_buttonbox.pack_end(self.apply_button,  expand=True, fill=True, padding=0)

    def exit_edit_mode(self, apply):
        if not self.in_edit_mode:
            return
        self.in_edit_mode = False
        self.onion_address_clickable_label.clickable = False
        for option_row in self.option_rows:
            option_row.stop_editing(apply)
        self.editing_buttonbox.remove(self.cancel_edit_button)
        self.editing_buttonbox.remove(self.apply_button)
        self.editing_buttonbox.pack_end(self.edit_button, expand=True, fill=True, padding=0)

    def on_copy_entry_clicked(self, entry, icon, event):
        entry.select_region(0, -1)
        entry.copy_clipboard()

    def on_switch_service_start_stop_state_set(self, switch, status):
        logging.debug("on_switch_service_start_stop_state_set. status: %r", status)
        self.service.run_threaded_when_idle(self.on_switch_state_set, status)

    def on_switch_state_set(self, status):
        self.update_onion_address_widget()
        self.set_connection_info_sensitivity()

        is_running = self.service.is_running
        logging.debug("is running: %r", is_running)
        if status and not is_running:
            success = self.ensure_not_in_edit_mode()
            if not success:
                return
            self.service.run_threaded(self.service.enable)
            self.show()
        if not status and is_running:
            self.service.run_threaded(self.service.disable)

    def ensure_not_in_edit_mode(self):
        if not self.in_edit_mode:
            return True

        changes = self.get_changes()
        logging.debug("Changes: %r", changes)
        if not changes:
            self.exit_edit_mode(apply=False)
            return True

        answer = self.gui.confirm_apply_changes()
        logging.debug("answer: %r", answer)
        if answer == "cancel":
            self.set_switch_status(False)
            return False
        apply = answer == "yes"
        self.exit_edit_mode(apply)
        return True

    def on_button_edit_clicked(self, button):
        self.enter_edit_mode()

    def on_button_apply_clicked(self, button):
        changes = self.get_changes()
        logging.debug("Changes: %r", changes)
        if not changes:
            self.exit_edit_mode(apply=False)
            return

        if self.switch.get_active():
            answer = self.gui.confirm_restart_service()
            if answer == "yes":
                def apply_changes():
                    self.apply_options_with_restarting()
                    self.exit_edit_mode(apply=True)
                self.service.run_threaded_when_idle(apply_changes)
            elif answer == "no":
                self.exit_edit_mode(apply=False)
            return

        self.apply_options()
        self.exit_edit_mode(apply=True)

    def on_button_cancel_edit_clicked(self, button):
        self.exit_edit_mode(apply=False)

    def on_checkbutton_persistence_toggled(self, checkbutton):
        self.update_autorun_checkbox()

    def on_button_copy_connection_info_clicked(self, button):
        text = self.service.connection_info
        self.gui.clipboard.set_text(text, len(text))

    def on_button_connection_info_clicked(self, button):
        text = self.service.connection_info

        builder = Gtk.Builder()
        builder.set_translation_domain(APP_NAME)
        builder.add_from_file(CONNECTION_INFO_UI_FILE)
        builder.connect_signals(self)
        textbuffer = builder.get_object("textbuffer")
        # XXX: Do we have to set a length here? Make sure this is overflow resistant.
        textbuffer.set_text(text, length=-1)
        # textview = builder.get_object("textview")
        window = builder.get_object("dialog")
        window.set_transient_for(self.gui.window)
        window.show_all()

    def on_close_button_clicked(self, window):
        window.close()

    def on_copy_connection_info_button_clicked(self, window):
        text = self.service.connection_info
        self.gui.clipboard.set_text(text, len(text))
        window.close()

    def on_button_onion_address_clicked(self, button):
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