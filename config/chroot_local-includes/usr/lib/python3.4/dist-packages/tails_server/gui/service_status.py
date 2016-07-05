import logging
from gi.repository import GLib, Gtk, GObject

from tails_server import dbus_interface
from tails_server import tor_util
from tails_server.exceptions import InvalidStatusError
from tails_server.config import TOR_BOOTSTRAPPED_TARGET
from tails_server.config import STATUS_UI_FILE

STATUS_STARTING = "Starting"
STATUS_RUNNING = "Running"
STATUS_STOPPING = "Stopping"
STATUS_STOPPED = "Stopped"

STATUS_PUBLISHING = "Connecting to Tor"
STATUS_ONLINE = "Online"
STATUS_OFFLINE = "Offline"

STATUS_INSTALLING = "Installing"
STATUS_INSTALLED = "Installed"
STATUS_UNINSTALLING = "Uninstalling"
STATUS_UNINSTALLED = "Not installed"

STATUS_TOR_IS_NOT_RUNNING = "Tor is not running"
STATUS_TOR_IS_RUNNING = "Tor is running"
STATUS_ERROR = "An error occurred. See the log for details."
STATUS_INVALID = "The service is in an invalid state. See the log for details."

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

    def __init__(self, service):
        super().__init__()
        self.service = service
        self.connect("update", self.on_update)
        self.dbus_monitor = dbus_interface.StatusMonitor(self.service.systemd_service,
                                                         self.dbus_receiver)
        self.tor_dbus_monitor = dbus_interface.StatusMonitor(TOR_BOOTSTRAPPED_TARGET,
                                                             self.tor_dbus_receiver)
        self.service_status = str()
        self.onion_status = str()
        self.tor_status = str()
        self.installation_status = str()
        self.status = str()

    def on_update(self, obj, status):
        logging.debug("New status for service %r: %r", self.service.name, status)
        GLib.idle_add(self.update, status)

    def update(self, status):
        self.update_substates(status)

        if status in [STATUS_ERROR, STATUS_INVALID]:
            new_status = status
        else:
            new_status = self.get_status_from_substates()
        if new_status == self.status:
            return
        self.status = new_status
        self.update_config_panel()
        self.update_service_list()

    def get_status_from_substates(self):
        if self.tor_status != STATUS_TOR_IS_RUNNING:
            logging.debug("Setting status to tor status %r", self.tor_status)
            return self.tor_status
        elif self.installation_status != STATUS_INSTALLED:
            logging.debug("Setting status to installation status %r", self.installation_status)
            return self.installation_status
        elif self.service_status != STATUS_RUNNING:
            logging.debug("Setting status to service status %r", self.service_status)
            return self.service_status
        else:
            logging.debug("Setting status to onion status %r", self.onion_status)
            return self.onion_status

    def update_substates(self, status):
        if status in [STATUS_TOR_IS_RUNNING,
                      STATUS_TOR_IS_NOT_RUNNING]:
            self.tor_status = status
        elif status in [STATUS_ONLINE,
                        STATUS_OFFLINE,
                        STATUS_PUBLISHING]:
            self.onion_status = status
        elif status in [STATUS_STARTING,
                        STATUS_STOPPING,
                        STATUS_STOPPED,
                        STATUS_RUNNING]:
            self.service_status = status
        elif status in [STATUS_INSTALLING,
                        STATUS_INSTALLED,
                        STATUS_UNINSTALLING,
                        STATUS_UNINSTALLED]:
            self.installation_status = status

    def update_config_panel(self):
        builder = self.service.config_panel.builder
        box = builder.get_object("box_status")
        label = builder.get_object("label_status_value")
        visual_widget = self.get_visual_widget(self.status)

        for child in box.get_children():
            box.remove(child)

        label.set_label(self.status)

        box.pack_start(visual_widget, expand=False, fill=False, padding=0)
        box.pack_start(label, expand=False, fill=False, padding=0)
        # XXX: Find out why the status only refreshes after config_panel.show() and do something
        # more lightweight
        if self.service.config_panel.is_active:
            self.service.config_panel.show()

    def update_service_list(self):
        try:
            service_row = self.service.gui.service_list.service_row_dict[self.service]
        except KeyError:
            return
        builder = service_row.builder
        box = builder.get_object("box_status_inner")
        label = builder.get_object("label_status_value")

        for child in box.get_children():
            box.remove(child)

        visual_widget = self.get_visual_widget(self.status)
        label_value = None
        if self.status in (STATUS_OFFLINE, STATUS_STOPPED):
            label_value = "Off"
        if self.status in (STATUS_ONLINE,):
            label_value = "On"

        if visual_widget:
            box.pack_start(visual_widget, expand=False, fill=False, padding=0)
        if label_value:
            label.set_label(label_value)
            box.pack_start(label, expand=False, fill=False, padding=0)

    def get_visual_widget(self, status):
        new_builder = Gtk.Builder()
        new_builder.add_from_file(STATUS_UI_FILE)
        if status in (STATUS_STARTING, STATUS_STOPPING, STATUS_INSTALLING,
                      STATUS_UNINSTALLING, STATUS_PUBLISHING):
            return new_builder.get_object("spinner")
        if status in (STATUS_OFFLINE, STATUS_STOPPED):
            return new_builder.get_object("image_off")
        if status == STATUS_ONLINE:
            return new_builder.get_object("image_on")
        if status in (STATUS_ERROR, STATUS_TOR_IS_NOT_RUNNING):
            return new_builder.get_object("image_error")
        raise InvalidStatusError("No visual widget for status %r defined" % status)

    def dbus_receiver(self, status):
        """Receives systemd status value from dbus and sets the status accordingly.
        valid status values: "active", "activating", "inactive", "deactivating"""

        if status == "activating":
            self.emit("update", STATUS_STARTING)
        if status == "active":
            self.emit("update", STATUS_RUNNING)
        if status == "deactivating":
            self.emit("update", STATUS_STOPPING)
        if status == "inactive":
            self.emit("update", STATUS_STOPPED)

    def tor_dbus_receiver(self, status):
        if status == "inactive":
            self.emit("update", STATUS_TOR_IS_NOT_RUNNING)
        if status == "active":
            self.emit("update", STATUS_TOR_IS_RUNNING)

    def guess_status(self):
        self.installation_status = STATUS_INSTALLED if self.service.is_installed \
            else STATUS_UNINSTALLED

        self.service_status = STATUS_RUNNING if self.service.is_running \
            else STATUS_STOPPED

        self.tor_status = STATUS_TOR_IS_RUNNING if tor_util.tor_has_bootstrapped() \
            else STATUS_TOR_IS_NOT_RUNNING

        if self.service.address and self.service.is_published:
            self.onion_status = STATUS_ONLINE
        else:
            self.onion_status = STATUS_OFFLINE

        # if not self.service.address or not self.service.is_published:
        #     self.service.run_threaded(self.service.add_onion)
        #     self.service.config_panel.set_switch_status(True)
        #     return

        self.emit("update", self.get_status_from_substates())