import logging
import threading
import time

from gi.repository import GLib, Gtk

from tails_server.exceptions import TorIsNotRunningError
from tails_server.gui.config_panel import ServiceConfigPanel
from tails_server.gui.service_status import *


class ServiceDecorator(object):

    status_row = None

    def __init__(self, gui, service):
        self.gui = gui
        self.service = service
        self.status = ServiceStatus(self)
        try:
            self.config_panel = ServiceConfigPanel(self.gui, self)
        except AttributeError as e:
            # XXX: This is a workaround for a bug in Python which blames all AttributeErrors on
            # __getattr__, if a custom __getattr__ was defined.
            raise Exception(e)

    def __getattr__(self, item):
        return getattr(self.service, item)

    def install(self):
        if not tor_util.tor_has_bootstrapped():
            self.status.emit("update", STATUS_TOR_IS_NOT_RUNNING)
            while not tor_util.tor_has_bootstrapped():
                time.sleep(1)
        self.status.emit("update", STATUS_INSTALLING)
        self.service.install()
        self.status.emit("update", STATUS_INSTALLED)
        GLib.idle_add(self.config_panel.on_service_installed)

    def uninstall(self):
        if self.service.is_running:
            self.service.disable()
        self.status.emit("update", STATUS_UNINSTALLING)
        self.stop_status_monitor()
        self.service.uninstall()
        self.config_panel = None

    def enable(self):
        self.status.emit("update", STATUS_STARTING)
        try:
            self.service.enable(skip_add_onion=True)
            self.add_onion()
        except TorIsNotRunningError:
            self.status.emit("update", STATUS_TOR_IS_NOT_RUNNING)

    def add_onion(self):
        self.status.emit("update", STATUS_PUBLISHING)
        self.service.add_onion()
        if self.service.is_running:
            self.status.emit("update", STATUS_ONLINE)
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
            self.status.emit("update", STATUS_ERROR)
            raise

