import abc
import logging

from gi.repository import Gtk, Gdk

from tails_server.config import APP_NAME, SERVICE_OPTION_UI_FILE


class OptionRow(object, metaclass=abc.ABCMeta):
    known_options_widgets = {
        "persistence": ("label_persistence", "box_persistence", "checkbutton_persistence", bool),
        "autostart": ("label_autostart", "box_autostart", "checkbutton_autostart", bool),
        # "allow-lan": ("label_allow_lan", "box_allow_lan", "checkbutton_allow_lan"),
    }

    masked_value = None

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

    def set_text(self, value):
        if self.option.masked:
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
        if self.option.masked:
            self.masked_value = self.option.value
        self.value_widget = None
        self.label = None
        self.box = None

    def show(self):
        self.label.show_all()
        self.box.show_all()


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
        logging.debug("Making %r not clickable", self.button)
        self.container.remove(self.button)
        self.button_box.remove(self.label)
        # self.value_widget.set_padding(0, 4)
        self.container.pack_start(self.label, expand=True, fill=True, padding=9)
        self.button_box.remove(self.image)
        self.container.pack_end(self.image, expand=False, fill=False, padding=9)
        self.label.set_selectable(True)
        self.image.set_visible(False)
        self._clickable = False

    def _make_clickable(self):
        logging.debug("Making %r clickable", self.button)
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
        self._clickable = True


class KnownOptionRow(OptionRow):
    def __init__(self, config_panel, option):
        super().__init__(config_panel, option)
        label, box, value_widget, type_ = self.known_options_widgets[option.name]
        self.label = self.config_panel.builder.get_object(label)
        self.label.unparent()
        self.box = self.config_panel.builder.get_object(box)
        self.box.unparent()
        self.value_widget = self.config_panel.builder.get_object(value_widget)
        if type_ == bool:
            self.value_widget.set_active(option.value)
        elif type in (str, int):
            self.value_widget.set_text(str(option.value))

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
        self.box.pack_end(self.value_widget, expand=True, fill=True, padding=5)


class EditableOptionRow(UnknownOptionRow):
    @property
    def sensitive(self):
        return self.clickable_label.clickable

    @sensitive.setter
    def sensitive(self, value):
        self.clickable_label.clickable = value
        if not self.option.masked:
            return
        show_button = self.builder.get_object("togglebutton_show")
        if not value:
            self.box.pack_end(show_button, expand=False, fill=False, padding=0)
        else:
            self.box.remove(show_button)

    def __init__(self, config_panel, option):
        super().__init__(config_panel, option)
        self.builder = Gtk.Builder()
        self.builder.set_translation_domain(APP_NAME)
        self.builder.add_from_file(SERVICE_OPTION_UI_FILE)
        self.builder.connect_signals(self)
        self.value_widget = self.builder.get_object("value_label")
        self.set_text(str(self.option.value))
        self.value_button = self.builder.get_object("value_button")
        self.image_edit = self.builder.get_object("image_edit")
        self.entry = self.builder.get_object("entry")
        self.button_box = self.builder.get_object("value_button_box")
        self.clickable_label = ClickableLabel(self.box, self.value_button, self.button_box,
                                              self.value_widget, self.image_edit)
        self._in_stop_editing = False
        self._button_pressed = False

    def on_togglebutton_show_toggled(self, button):
        if button.get_active():
            self.set_unmasked_text(self.masked_value)
        else:
            self.set_masked_text(self.masked_value)

    def on_entry_key_press_event(self, widget, event):
        key_name = Gdk.keyval_name(event.keyval)
        logging.log(5, "Event: Key pressed: %r", key_name)
        if key_name == "Return":
            self.stop_editing()
        if key_name == "Escape":
            self.stop_editing(apply=False)

    def on_value_button_event(self, widget, event):
        logging.log(3, "Event: Value button event: %r", event)
        if event.type == Gdk.EventType.BUTTON_PRESS:
            logging.log(5, "Before button press. Button is pressed in: %r", widget.get_active())
            self._button_pressed = True

    def on_value_button_toggled(self, button):
        logging.log(5, "Event: Value button toggled. is pressed in: %r", button.get_active())
        if not self.clickable_label.clickable:
            return True
        if self.value_button.get_active():
            self.start_editing()
        else:
            self.stop_editing()

    def on_value_button_event_after(self, widget, event):
        if event.type == Gdk.EventType.BUTTON_RELEASE:
            logging.log(5, "After button press")
            self._button_pressed = False

    def on_entry_focus_out_event(self, widget, event):
        if self._button_pressed:
            return
        logging.log(5, "Entering entry focus out event %r", event)
        self.stop_editing()
        self.value_button.set_active(False)
        logging.log(5, "Exiting entry focus out event %r", event)

    def stop_editing(self, apply=True):
        if self._in_stop_editing or self.value_widget in self.button_box.get_children():
            return
        logging.log(5, "Entering stop editing")
        self._in_stop_editing = True
        if apply:
            value = self.entry.get_text()
            self.masked_value = value
            self.set_text(value)
            self.option.value = value
        self.button_box.remove(self.entry)
        self.button_box.pack_start(self.value_widget, expand=True, fill=True, padding=0)
        self.image_edit.set_from_stock("gtk-edit", Gtk.IconSize.BUTTON)
        self._in_stop_editing = False
        logging.log(5, "Exiting stop editing")

    def start_editing(self):
        logging.log(5, "Entering start editing")
        self.entry.set_text(str(self.option.value))
        self.button_box.remove(self.value_widget)
        self.button_box.pack_start(self.entry, expand=True, fill=True, padding=0)
        self.image_edit.set_from_stock("gtk-apply", Gtk.IconSize.BUTTON)
        self.entry.grab_focus()
        logging.log(5, "Exiting start editing")
