import logging
import threading
import time

from gi.repository import GLib

from tails_server import tor_util
from tails_server.gui.config_panel import ServiceConfigPanel
from tails_server.gui.service_status import Status, ServiceStatus

# Only required for type hints
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from tails_server.service_template import TailsService


class ServiceDecorator(object):
    """Service class extended by functions used in the GUI"""

    status_row = None

    def __init__(self, gui, service: "TailsService"):
        self.gui = gui
        self.service = service
        self.status = ServiceStatus(self)
        self.lock = threading.Lock()

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
            self.status.emit("update", Status.tor_is_not_running)
            while not tor_util.tor_has_bootstrapped():
                time.sleep(1)
        self.status.emit("update", Status.installing)
        self.service.install()
        self.status.emit("update", Status.installed)
        GLib.idle_add(self.config_panel.on_service_installed)

    def uninstall(self):
        self.status.emit("update", Status.uninstalling)
        self.status.stop_monitoring()
        self.service.uninstall()
        self.config_panel = None

    def enable(self):
        if not tor_util.tor_has_bootstrapped():
            self.status.emit("update", Status.tor_is_not_running)
            return

        if self.service.publish_hs_before_starting:
            if not self.service.is_published:
                self.create_hidden_service()
            if not self.service.is_running:
                self.start()
        else:
            if not self.service.is_running:
                self.start()
            if not self.service.is_published:
                self.create_hidden_service()

    def start(self):
        with self.lock:
            self.status.emit("update", Status.starting)
            self.service.start()
            if self.service.is_running and self.service.is_published:
                self.status.emit("update", Status.online)

    def on_started(self):
        for option_row in self.config_panel.option_rows:
            if option_row.option.reload_after_service_started:
                logging.info("Reloading option %r because service %r was successfully started",
                             option_row.option.name, self.service.name)
                option_row.reload_value()

    def create_hidden_service(self):
        with self.lock:
            self.status.emit("update", Status.publishing)
        self.service.create_hidden_service()
        if not self.service.publish_hs_before_starting:
            logging.debug("Removing newly created onion address because service %r stopped",
                          self.name)
            self.remove_hidden_service()
        with self.lock:
            if self.service.is_running and self.service.is_published:
                self.status.emit("update", Status.online)

    def disable(self):
        self.service.disable()
        self.status.emit("update", Status.offline)

    def run_threaded(self, function, *args):
        """Run the specified function in a new thread"""
        thread = threading.Thread(target=self.run_with_exception_handling,
                                  args=(function,) + args)
        thread.daemon = True
        thread.start()

    def run_threaded_when_idle(self, function, *args):
        """Run the specified function wrapped in a GLib.idle_add() call in a new thread"""
        thread = threading.Thread(target=self.run_with_exception_handling,
                                  args=(GLib.idle_add, function) + args)
        thread.daemon = True
        thread.start()

    def run_with_exception_handling(self, function, *args):
        try:
            function(*args)
        except:
            logging.exception("Got exception on thread handler")
            self.status.emit("update", Status.error)
