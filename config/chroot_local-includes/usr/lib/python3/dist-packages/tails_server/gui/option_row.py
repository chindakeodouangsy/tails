import abc
import logging

from gi.repository import Gtk

from tails_server.config import APP_NAME, SERVICE_OPTION_UI_FILE

# Only required for type hints
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from tails_server.option_template import TailsServiceOption

class OptionRow(object, metaclass=abc.ABCMeta):
    known_options_widgets = {
        "persistence": ("label_persistence", "box_persistence", "checkbutton_persistence", bool),
        "autostart": ("label_autostart", "box_autostart", "checkbutton_autostart", bool),
        # "allow-lan": ("label_allow_lan", "box_allow_lan", "checkbutton_allow_lan"),
        # "server-password": ("label_password", "box_password", "label_password_value", str)
    }

    masked_value = None
    show_unmasked = False

    @property
    def sensitive(self):
        return self.box.get_sensitive()

    @sensitive.setter
    def sensitive(self, value):
        self.box.set_sensitive(value)

    @property
    def value(self):
        if self.option.masked:
            return self.masked_value
        if self.option.type == str:
            return self.value_widget.get_text()
        elif self.option.type == int:
            return int(self.value_widget.get_text())
        elif self.option.type == bool:
            return self.value_widget.get_active()

    @property
    def editable(self):
        return self._editable

    @property
    def edited_value(self):
        return self.value

    def set_text(self, value):
        if self.option.masked and not self.show_unmasked:
            self.set_masked_text(value)
        else:
            self.set_unmasked_text(value)

    def set_unmasked_text(self, value):
        self.value_widget.set_text(value)

    def set_masked_text(self, value):
        self.value_widget.set_text("*" * len(value))

    @classmethod
    def create(cls, config_panel, option):
        if option.name in cls.known_options_widgets:
            type_ = cls.known_options_widgets[option.name][3]
            return cls.create_known_option_row(config_panel, option, type_)
        else:
            return cls.create_unknown_option_row(config_panel, option)

    @classmethod
    def create_known_option_row(cls, config_panel, option, type_):
        if type_ in [str, int]:
            return KnownTextOptionRow(config_panel, option)
        if type_ == bool:
            return KnownBooleanOptionRow(config_panel, option)
        raise TypeError("Can't display option %r of type %r", option.name, option.type)

    @classmethod
    def create_unknown_option_row(cls, config_panel, option):
        if option.type in [str, int]:
            return UnknownTextOptionRow(config_panel, option)
        if option.type == bool:
            return UnknownBooleanOptionRow(config_panel, option)
        raise TypeError("Can't display option %r of type %r", option.name, option.type)

    def __init__(self, config_panel, option: "TailsServiceOption"):
        self.config_panel = config_panel
        self.option = option
        if self.option.masked:
            self.masked_value = self.option.value
        self.value_widget = None
        self.label = None
        self.box = None
        self._editable = False

    def show(self):
        self.label.show_all()
        self.box.show_all()

    def get_change(self):
        if self.option.value != self.edited_value:
            logging.debug("Option %r has changed. Old value: %r; New value: %r", self.option.name,
                          self.option.value, self.edited_value)
            return self.option.value, self.edited_value


class ClickableLabel(object):
    @property
    def clickable(self):
        return self._clickable

    @clickable.setter
    def clickable(self, value):
        if self._clickable == value:
            return
        if value:
            self._make_clickable()
        else:
            self._make_not_clickable()

    def __init__(self, container, button, button_box, label, image):
        self.container = container
        self.container.set_size_request(width=-1, height=34)
        self.button = button
        self.button_box = button_box
        self.label = label
        self.image = image
        self._clickable = True
        self._make_clickable()

    def _make_not_clickable(self):
        self.container.remove(self.button)
        self.button_box.remove(self.label)
        # self.value_widget.set_padding(0, 4)
        self.container.pack_start(self.label, expand=True, fill=True, padding=9)
        self.button_box.remove(self.image)
        self.container.pack_end(self.image, expand=False, fill=False, padding=9)
        self.label.set_selectable(True)
        self.image.set_visible(False)
        self.image.set_no_show_all(True)
        self._clickable = False

    def _make_clickable(self):
        if not self._clickable:
            self.container.remove(self.label)
            self.container.remove(self.image)
        for child in self.container.get_children():
            self.container.remove(child)
        for child in self.button_box.get_children():
            self.button_box.remove(child)
        self.button_box.pack_start(self.label, expand=True, fill=True, padding=0)
        self.button_box.pack_end(self.image, expand=False, fill=False, padding=0)
        self.container.pack_start(self.button, expand=True, fill=True, padding=0)
        self.label.set_selectable(False)
        self.image.set_visible(True)
        self.image.set_no_show_all(False)
        self._clickable = True


class BooleanOptionRow(OptionRow):
    def __init__(self, config_panel, option):
        super().__init__(config_panel, option)

    @property
    def value(self):
        return self.value_widget.get_active()

    def load_value(self):
        self.value_widget.set_active(self.option.value)

    def start_editing(self):
        logging.log(5, "Entering start editing")
        self.value_widget.set_sensitive(True)
        self._editable = True
        logging.log(5, "Exiting start editing")

    def stop_editing(self, apply=True):
        logging.log(5, "Entering stop editing")
        if apply:
            self.option.value = self.value
        else:
            self.value_widget.set_active(self.option.value)
        self.value_widget.set_sensitive(False)
        self._editable = False
        logging.log(5, "Exiting stop editing")


class TextOptionRow(OptionRow):

    entry = None
    togglebutton_show = None

    def load_value(self):
        self.set_text(str(self.option.value))

    def reload_value(self):
        self.option.reload()
        self.set_text(str(self.option.value))

    @property
    def edited_value(self):
        return self.option.type(self.entry.get_text())

    def stop_editing(self, apply=True):
        logging.log(5, "Entering stop editing")
        if apply:
            value = self.entry.get_text()
            self.masked_value = value
            self.set_text(value)
            self.option.value = value
        self.box.remove(self.entry)
        self.box.pack_start(self.value_widget, expand=True, fill=True, padding=9)
        self._editable = False
        logging.log(5, "Exiting stop editing")

    def start_editing(self):
        logging.log(5, "Entering start editing")
        self.entry.set_text(str(self.option.value))
        if self.option.masked:
            self.entry.set_visibility(self.togglebutton_show.get_active())
        self.box.remove(self.value_widget)
        self.box.pack_start(self.entry, expand=True, fill=True, padding=0)
        self._editable = True
        # self.entry.grab_focus()
        logging.log(5, "Exiting start editing")


class KnownOptionRow(OptionRow):
    def __init__(self, config_panel, option):
        super().__init__(config_panel, option)
        label, box, value_widget, cls = self.known_options_widgets[option.name]
        self.label = self.config_panel.builder.get_object(label)
        self.label.unparent()
        self.box = self.config_panel.builder.get_object(box)
        self.box.unparent()
        self.value_widget = self.config_panel.builder.get_object(value_widget)
        self.config_panel.builder.connect_signals(self.config_panel)


class KnownBooleanOptionRow(KnownOptionRow, BooleanOptionRow):
    def __init__(self, config_panel, option):
        super().__init__(config_panel, option)
        self.load_value()


class KnownTextOptionRow(KnownOptionRow, TextOptionRow):
    def __init__(self, config_panel, option):
        super().__init__(config_panel, option)
        self.load_value()


class UnknownOptionRow(OptionRow):
    def __init__(self, config_panel, option):
        super().__init__(config_panel, option)
        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.label = Gtk.Label(option.name_in_gui)
        self.label.set_alignment(xalign=1, yalign=0.5)
        self.label.set_sensitive(False)


class UnknownBooleanOptionRow(UnknownOptionRow, BooleanOptionRow):
    def __init__(self, config_panel, option):
        super().__init__(config_panel, option)
        self.value_widget = Gtk.CheckButton()
        self.value_widget.set_sensitive(False)
        self.box.pack_end(self.value_widget, expand=True, fill=True, padding=9)
        self.load_value()


class UnknownTextOptionRow(UnknownOptionRow, TextOptionRow):
    def __init__(self, config_panel, option):
        super().__init__(config_panel, option)
        self.builder = Gtk.Builder()
        self.builder.set_translation_domain(APP_NAME)
        self.builder.add_from_file(SERVICE_OPTION_UI_FILE)
        self.builder.connect_signals(self)
        self.value_widget = self.builder.get_object("value_label")
        self.value_widget.set_size_request(-1, 21)
        self.entry = self.builder.get_object("entry")
        self.box.pack_start(self.value_widget, expand=True, fill=True, padding=9)
        if self.option.masked:
            self.togglebutton_show = self.builder.get_object("togglebutton_show")
            self.box.pack_end(self.togglebutton_show, expand=False, fill=False, padding=0)
        self.load_value()

    def on_togglebutton_show_toggled(self, button):
        self.show_unmasked = button.get_active()

        if self.editable:
            self.entry.set_visibility(button.get_active())
            return

        if button.get_active():
            self.set_unmasked_text(self.masked_value)
        else:
            self.set_masked_text(self.masked_value)


