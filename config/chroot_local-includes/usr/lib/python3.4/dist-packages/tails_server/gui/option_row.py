import abc
import logging

from gi.repository import Gtk


class OptionRow(object, metaclass=abc.ABCMeta):
    known_options_widgets = {
        "persistence": ("label_persistence", "box_persistence", "checkbutton_persistence"),
        "autostart": ("label_autostart", "box_autostart", "checkbutton_autostart"),
        # "allow-lan": ("label_allow_lan", "box_allow_lan", "checkbutton_allow_lan"),
    }

    @property
    def sensitive(self):
        return self.box.get_sensitive()

    @sensitive.setter
    def sensitive(self, value):
        self.box.set_sensitive(value)

    @property
    def value(self):
        if self.option.type == str:
            return self.value_widget.get_text()
        elif self.option.type == int:
            return int(self.value_widget.get_text())
        elif self.option.type == bool:
            return self.value_widget.get_active()

    @classmethod
    def create(cls, config_panel, option):
        if option.name in cls.known_options_widgets:
            return KnownOptionRow(config_panel, option)
        if option.type in [str, int]:
            return EditableOptionRow(config_panel, option)
        if option.type == bool:
            return BooleanOptionRow(config_panel, option)
        raise TypeError("Can't display option %r of type %r", option.name, option.type)

    def __init__(self, config_panel, option):
        self.config_panel = config_panel
        self.option = option
        logging.debug("Adding option %r to GUI", option.name)
        logging.debug("%r.value: %r", option.name, option.value)
        self.value_widget = None
        self.label = None
        self.box = None

    def show(self):
        self.label.show_all()
        self.box.show_all()


class KnownOptionRow(OptionRow):
    def __init__(self, config_panel, option):
        super().__init__(config_panel, option)
        label, box, value_widget = self.known_options_widgets[option.name]
        self.label = self.config_panel.builder.get_object(label)
        self.label.unparent()
        self.box = self.config_panel.builder.get_object(box)
        self.box.unparent()
        self.value_widget = self.config_panel.builder.get_object(value_widget)
        self.config_panel.builder.connect_signals(self.config_panel)


class UnknownOptionRow(OptionRow):
    def __init__(self, config_panel, option):
        super().__init__(config_panel, option)
        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.label = Gtk.Label(option.name_in_gui)
        self.label.set_alignment(xalign=1, yalign=0.5)
        self.label.set_sensitive(False)


class BooleanOptionRow(UnknownOptionRow):
    @property
    def value(self):
        return self.value_widget.get_active()

    def __init__(self, config_panel, option):
        super().__init__(config_panel, option)
        self.value_widget = Gtk.CheckButton()
        self.value_widget.set_active(option.value)
        self.box.pack_end(self.value_widget, expand=True, fill=True, padding=0)


class EditableOptionRow(UnknownOptionRow):
    def __init__(self, config_panel, option):
        super().__init__(config_panel, option)
        self.value_widget = Gtk.Entry(text=option.value)
        self.value_widget.set_text(str(option.value))
        self.box.pack_end(self.value_widget, expand=True, fill=True, padding=0)
