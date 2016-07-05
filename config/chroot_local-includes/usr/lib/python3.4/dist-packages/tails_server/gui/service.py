import logging
import threading
import time

from gi.repository import GLib, Gtk, GObject

from tails_server import tor_util, dbus_interface
from tails_server.exceptions import TorIsNotRunningError
from tails_server.gui.config_panel import ServiceConfigPanel

from tails_server.config import TOR_BOOTSTRAPPED_TARGET
from tails_server.config import STATUS_UI_FILE


class ServiceDecorator(object):

    status_row = None
    _config_panel = None

    @property
    def config_panel(self):
        if not self._config_panel:
            logging.debug("Instantiating config panel for service %r", self.service.name)
            try:
                self._config_panel = ServiceConfigPanel(self.gui, self)
            except AttributeError as e:
                # XXX: This is a workaround for a bug in Python which blames all AttributeErrors on
                # __getattr__, if a custom __getattr__ was defined.
                raise Exception(e)
        return self._config_panel

    def __init__(self, gui, service):
        self.gui = gui
        self.service = service
        self.status = ServiceStatus(self)

    def __getattr__(self, item):
        return getattr(self.service, item)

    def install(self):
        if not tor_util.tor_has_bootstrapped():
            self.status.emit("update", ServiceStatus.STATUS_TOR_IS_NOT_RUNNING)
            while not tor_util.tor_has_bootstrapped():
                time.sleep(1)
        self.status.emit("update", ServiceStatus.STATUS_INSTALLING)
        self.service.install()
        self.status.emit("update", ServiceStatus.STATUS_OFFLINE)
        GLib.idle_add(self.config_panel.on_service_installed)

    def uninstall(self):
        if self.service.is_running:
            self.service.disable()
        self.status.emit("update", ServiceStatus.STATUS_UNINSTALLING)
        self._config_panel = None
        self.stop_status_monitor()
        self.service.uninstall()

    def enable(self):
        self.status.emit("update", ServiceStatus.STATUS_STARTING)
        try:
            self.service.enable(skip_add_onion=True)
            self.add_onion()
        except TorIsNotRunningError:
            self.status.emit("update", ServiceStatus.STATUS_TOR_IS_NOT_RUNNING)

    def add_onion(self):
        self.status.emit("update", ServiceStatus.STATUS_PUBLISHING)
        self.service.add_onion()
        if self.service.is_running:
            self.status.emit("update", ServiceStatus.STATUS_ONLINE)
        else:
            logging.debug("Removing newly created onion address because service %r stopped",
                          self.name)
            self.remove_onion()

    def activate_status_monitor(self):
        self.status.dbus_monitor.run()
        self.status.tor_dbus_monitor.run()

    def stop_status_monitor(self):
        self.status.dbus_monitor.stop()
        self.status.tor_dbus_monitor.stop()

    def run_threaded(self, function, *args):
        thread = threading.Thread(target=self.run_with_exception_handling,
                                  args=(function,) + args)
        thread.daemon = True
        thread.start()

    def run_threaded_when_idle(self, function, *args):
        thread = threading.Thread(target=self.run_with_exception_handling,
                                  args=(GLib.idle_add, function) + args)
        thread.daemon = True
        thread.start()

    def run_with_exception_handling(self, function, *args):
        try:
            function(*args)
        except:
            self.status.emit("update", self.status.STATUS_ERROR)
            raise


class ServiceStatus(Gtk.Widget):

    @classmethod
    def register_signal(cls):
        GObject.signal_new(
            "update",       # signal name
            ServiceStatus,  # object type
            GObject.SIGNAL_RUN_FIRST | GObject.SIGNAL_ACTION,  # flags
            None,           # return type
            (str,),         # argument types
        )

    STATUS_STARTING = "Starting"
    STATUS_STOPPING = "Stopping"
    STATUS_INSTALLING = "Installing"
    STATUS_UNINSTALLING = "Uninstalling"
    STATUS_OFFLINE = "Offline"
    STATUS_STOPPED = "Stopped"
    STATUS_ONLINE = "Online"
    STATUS_PUBLISHING = "Connecting to Tor"
    STATUS_TOR_IS_NOT_RUNNING = "Tor is not running"
    STATUS_ERROR = "An error occurred. See the log for details."

    def __init__(self, service):
        super().__init__()
        self.service = service
        self.connect("update", self.on_update)
        self.dbus_monitor = dbus_interface.StatusMonitor(self.service.systemd_service,
                                                         self.dbus_receiver)
        self.tor_dbus_monitor = dbus_interface.StatusMonitor(TOR_BOOTSTRAPPED_TARGET,
                                                             self.tor_dbus_receiver)

    def on_update(self, obj, status):
        logging.debug("New status: %r", status)
        GLib.idle_add(self.update, status)

    def update(self, status):
        self.update_config_panel(status)
        self.update_service_list(status)

    def update_config_panel(self, status):
        builder = self.service.config_panel.builder
        box = builder.get_object("box_status")
        label = builder.get_object("label_status_value")
        visual_widget = self.get_visual_widget(status)

        for child in box.get_children():
            box.remove(child)

        label.set_label(status)

        box.pack_start(visual_widget, expand=False, fill=False, padding=0)
        box.pack_start(label, expand=False, fill=False, padding=0)
        # XXX: Find out why the status only refreshes after config_panel.show() and do something
        # more lightweight
        if self.service.config_panel.is_active:
            self.service.config_panel.show()

    def update_service_list(self, status):
        try:
            service_row = self.service.gui.service_list.service_row_dict[self.service]
        except KeyError:
            return
        builder = service_row.builder
        box = builder.get_object("box_status_inner")
        label = builder.get_object("label_status_value")

        for child in box.get_children():
            box.remove(child)

        visual_widget = self.get_visual_widget(status)
        label_value = None
        if status in (self.STATUS_OFFLINE, self.STATUS_STOPPED):
            label_value = "Off"
        if status in (self.STATUS_ONLINE,):
            label_value = "On"

        if visual_widget:
            box.pack_start(visual_widget, expand=False, fill=False, padding=0)
        if label_value:
            label.set_label(label_value)
            box.pack_start(label, expand=False, fill=False, padding=0)

    def get_visual_widget(self, status):
        new_builder = Gtk.Builder()
        new_builder.add_from_file(STATUS_UI_FILE)
        if status in (self.STATUS_STARTING, self.STATUS_STOPPING, self.STATUS_INSTALLING,
                      self.STATUS_UNINSTALLING, self.STATUS_PUBLISHING):
            return new_builder.get_object("spinner")
        if status in (self.STATUS_OFFLINE, self.STATUS_STOPPED):
            return new_builder.get_object("image_off")
        if status == self.STATUS_ONLINE:
            return new_builder.get_object("image_on")
        if status in (self.STATUS_ERROR, self.STATUS_TOR_IS_NOT_RUNNING):
            return new_builder.get_object("image_error")

    def dbus_receiver(self, status):
        """Receives systemd status value from dbus and sets the status accordingly.
        valid status values: "active", "activating", "inactive", "deactivating"""
        if status == "active":
            self.update(self.STATUS_ONLINE)
        if status == "inactive":
            self.update(self.STATUS_OFFLINE)
        if status == "activating":
            self.update(self.STATUS_STARTING)
        if status == "deactivating":
            self.update(self.STATUS_STOPPING)

    def tor_dbus_receiver(self, status):
        if status == "inactive":
            self.update(self.STATUS_TOR_IS_NOT_RUNNING)
        if status == "active":
            self.guess_status()

    def guess_status(self):
        if not self.service.is_installed:
            return
        if not self.service.is_running:
            self.update(self.STATUS_OFFLINE)
            self.service.config_panel.set_switch_status(False)
            return

        if not tor_util.tor_has_bootstrapped():
            self.update(self.STATUS_TOR_IS_NOT_RUNNING)
            return

        if not self.service.address or not self.service.is_published:
            self.service.run_threaded(self.service.add_onion)
            self.service.config_panel.set_switch_status(True)
            return

        self.update(self.STATUS_ONLINE)
        self.service.config_panel.set_switch_status(True)
