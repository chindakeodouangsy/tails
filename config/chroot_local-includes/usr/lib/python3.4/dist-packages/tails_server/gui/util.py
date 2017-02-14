from gi.repository import Gtk


class DisableOtherWindows(object):
    def __init__(self, window):
        assert(isinstance(window, Gtk.Window))
        self.window = window
        self.other_windows = [window for window in Gtk.Window.list_toplevels()
                              if window != self.window]
        self.other_window_sensitivities = list()

    def __enter__(self):
        self.disable_other_windows()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.reenable_other_windows()

    def disable_other_windows(self):
        for window in self.other_windows:
            self.other_window_sensitivities.append(window.get_sensitive())
            window.set_sensitive(False)

    def reenable_other_windows(self):
        for i, window in enumerate(self.other_windows):
                window.set_sensitive(self.other_window_sensitivities[i])
