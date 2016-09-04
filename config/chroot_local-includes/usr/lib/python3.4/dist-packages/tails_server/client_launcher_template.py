import abc
import logging
import subprocess
import os

from tails_server import _
from tails_server import util
from tails_server.config import HELPER_SCRIPTS_DIR

SET_CLIENT_AUTH_SCRIPT_NAME = os.path.join(HELPER_SCRIPTS_DIR, "set-hidden-service-auth")


class MissingArgumentsError(Exception):
    def __init__(self, missing_args, *args, **kwargs):
        message = ", ".join([arg.name for arg in missing_args])
        super().__init__(message, *args, **kwargs)
        self.missing_args = missing_args


class InvalidArgumentError(Exception):
    pass


class ClientLauncherDetail(object):
    def __init__(self, name, name_in_gui, type_, required=True):
        self.name = name
        self.name_in_gui = name_in_gui
        self.type = type_
        self.required = required


class ClientLauncher(metaclass=abc.ABCMeta):

    values = dict()

    @property
    @abc.abstractmethod
    def name(self):
        """The name of the service this client launcher belongs to."""
        return str()

    @property
    def name_in_gui(self):
        """The name of the client, as displayed in the GUI."""
        return self.name.capitalize()

    @property
    @abc.abstractmethod
    def icon_name(self):
        return str()

    details = [
        ClientLauncherDetail("address", _("Address"), str),
        ClientLauncherDetail("port", _("Port"), int),
        ClientLauncherDetail("client_cookie", _("Client Cookie"), str),
    ]

    @abc.abstractmethod
    def prepare(self):
        """Prepare everything for launching the client.
        IMPORTANT: While implementing this, be aware that all the values in self.values are user
        controlled!
        """
        logging.info("Preparing to launch %r with values %r", self.name, self.values)
        self.check_if_details_missing()
        self.check_if_details_sane()
        self.set_client_cookie()

    @abc.abstractmethod
    def launch(self):
        """Launch the client to connect to the service.
        IMPORTANT: While implementing this, be aware that all the values in self.values are user
        controlled!
        """
        self.prepare()
        logging.info("Trying to launch %r with values %r", self.name, self.values)

    def check_if_details_missing(self):
        missing_details = [detail for detail in self.details if detail.required and
                           detail.name not in self.values]
        if missing_details:
            raise MissingArgumentsError(missing_details)

    def check_if_details_sane(self):
        """Sanity check the values we are going to use. This should be extended by subclasses
        which use additional details to also check those."""
        if not util.is_valid_onion_address(self.values["address"]):
            raise InvalidArgumentError("'Address': %r" % self.values["address"])
        if not util.is_valid_port(self.values["port"]):
            raise InvalidArgumentError("'Address': %r" % self.values["address"])
        if not util.is_valid_client_cookie(self.values["client_cookie"]):
            raise InvalidArgumentError("'Client Cookie': %r" % self.values["client_cookie"])

    def set_client_cookie(self):
        cookie = self.values["client_cookie"]
        address = self.values["address"]
        logging.info("Setting client cookie for address %r to %r", address, cookie)
        # XXX: The cookie and address are user controlled, but because subprocess handles escaping
        # and quoting of arguments, this should still be secure.
        subprocess.check_call(["sudo", SET_CLIENT_AUTH_SCRIPT_NAME, address, cookie])
