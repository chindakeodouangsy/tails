from gi.repository import Gtk
from tails_server.config import APP_NAME, QUESTION_DIALOG_UI_FILE


class QuestionDialog(object):
    def __init__(self, parent, title, text, yes_label, no_label,
                 cancel_label=None, destructive=False):
        self.result = "cancel"

        self.builder = Gtk.Builder()
        self.builder.set_translation_domain(APP_NAME)
        self.builder.add_from_file(QUESTION_DIALOG_UI_FILE)
        self.builder.connect_signals(self)

        self.dialog = self.builder.get_object("dialog")
        self.dialog.set_transient_for(parent)
        self.dialog.set_title(title)

        text_label = self.builder.get_object("question_text")
        text_label.set_label(text)

        action_area = self.builder.get_object("dialog-action_area")

        yes_button = self.builder.get_object("yes_button")
        yes_button.set_label(yes_label)

        no_button = self.builder.get_object("no_button")
        no_button.set_label(no_label)

        cancel_button = self.builder.get_object("cancel_button")
        if cancel_label:
            cancel_button.set_label(cancel_label)
        else:
            action_area.remove(cancel_button)

        if destructive:
            yes_button_style_context = yes_button.get_style_context()
            yes_button_style_context.add_class(Gtk.STYLE_CLASS_DESTRUCTIVE_ACTION)

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


class RestartServiceQuestionDialog(QuestionDialog):
    def __init__(self, parent):
        title = "Restart Service"
        text = "You need to restart the service to apply changes. Do you want to restart the " \
               "service now?"
        yes_label = "Apply & Restart Service"
        no_label = "Discard Changes"
        cancel_label = "Cancel"
        super().__init__(parent, title, text, yes_label, no_label, cancel_label)


class ApplyChangesQuestionDialog(QuestionDialog):
    def __init__(self, parent):
        title = "Apply Changes"
        text = "You changed this service's options. Do you want to apply these changes?"
        yes_label = "Apply Changes"
        no_label = "Discard Changes"
        cancel_label = "Cancel"
        super().__init__(parent, title, text, yes_label, no_label, cancel_label)


class RemoveServiceQuestionDialog(QuestionDialog):
    def __init__(self, parent):
        title = "Remove service"
        text = "This will irrevocably delete all configurations and data of this service, " \
               "including the onion address. Are you sure you want to proceed?"
        yes_label = "Remove"
        no_label = "Cancel"
        super().__init__(parent, title, text, yes_label, no_label, cancel_label=False,
                         destructive=True)