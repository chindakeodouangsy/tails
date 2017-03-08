from gi.repository import Gtk

from tails_server import _
from tails_server.config import APP_NAME, QUESTION_DIALOG_UI_FILE


class Dialog(object):
    def __init__(self, parent, title, text, yes_label, no_label=None,
                 cancel_label=None):
        self.result = "cancel"

        self.builder = Gtk.Builder()
        self.builder.set_translation_domain(APP_NAME)
        self.builder.add_from_file(QUESTION_DIALOG_UI_FILE)
        self.builder.connect_signals(self)

        self.dialog = self.builder.get_object("dialog")
        self.dialog.set_transient_for(parent)
        self.dialog.set_title(title)

        self.text_label = self.builder.get_object("text")
        self.text_label.set_label(text)

        self.icon_image = self.builder.get_object("image")

        action_area = self.builder.get_object("dialog-action_area")

        self.yes_button = self.builder.get_object("yes_button")
        self.yes_button.set_label(yes_label)

        self.no_button = self.builder.get_object("no_button")
        if no_label:
            self.no_button.set_label(no_label)
        else:
            action_area.remove(self.no_button)

        self.cancel_button = self.builder.get_object("cancel_button")
        if cancel_label:
            self.cancel_button.set_label(cancel_label)
        else:
            action_area.remove(self.cancel_button)

    def run(self):
        self.dialog.run()
        return self.result

    def on_yes_button_clicked(self, button):
        self.result = "yes"
        self.dialog.close()

    def on_no_button_clicked(self, button):
        self.result = "no"
        self.dialog.close()

    def on_cancel_button_clicked(self, button):
        self.result = "cancel"
        self.dialog.close()

    def on_dialog_delete_event(self, widget, data=None):
        self.dialog.hide()


class ErrorDialog(Dialog):
    def __init__(self, parent, title, text):
        yes_label = _("OK")
        super().__init__(parent, title, text, yes_label)

        __, size = self.icon_image.get_icon_name()
        self.icon_image.set_from_stock("gtk-dialog-warning", size)


class QuestionDialog(Dialog):
    def __init__(self, parent, title, text, yes_label, no_label,
                 cancel_label=None, destructive=False):
        super().__init__(parent, title, text, yes_label, no_label, cancel_label)

        _, size = self.icon_image.get_icon_name()
        self.icon_image.set_from_stock("gtk-dialog-question", size)

        if destructive:
            yes_button_style_context = self.yes_button.get_style_context()
            yes_button_style_context.add_class(Gtk.STYLE_CLASS_DESTRUCTIVE_ACTION)


class RestartServiceQuestionDialog(QuestionDialog):
    def __init__(self, parent):
        title = _("Restart Service")
        text = _("You need to restart the service to apply changes. Do you want to restart the "
                 "service now?")
        yes_label = _("Apply & Restart Service")
        no_label = _("Discard Changes")
        cancel_label = _("Cancel")
        super().__init__(parent, title, text, yes_label, no_label, cancel_label)


class ApplyChangesQuestionDialog(QuestionDialog):
    def __init__(self, parent):
        title = _("Apply Changes")
        text = _("You changed this service's options. Do you want to apply these changes?")
        yes_label = _("Apply Changes")
        no_label = _("Discard Changes")
        cancel_label = _("Cancel")
        super().__init__(parent, title, text, yes_label, no_label, cancel_label)


class RemoveServiceQuestionDialog(QuestionDialog):
    def __init__(self, parent):
        title = _("Remove service")
        text = _("This will irrevocably <b>delete all configuration and data</b> of this service, "
                 "including the onion address.\n\n"
                 "Are you sure you want to proceed?")
        yes_label = _("Remove")
        no_label = _("Cancel")
        super().__init__(parent, title, text, yes_label, no_label, cancel_label=None,
                         destructive=True)
