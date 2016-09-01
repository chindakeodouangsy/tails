import abc
import logging

from tails_server import _


class DetailsMissingError(Exception):
    def __init__(self, missing_details, *args, **kwargs):
        message = ", ".join([detail.name for detail in missing_details])
        super().__init__(message, *args, **kwargs)
        self.missing_details = missing_details


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
    def launch(self):
        logging.info("Trying to launch %r with values %r", self.name, self.values)
        missing_details = [detail for detail in self.details if detail.required and
                           detail.name not in self.values]
        if missing_details:
            raise DetailsMissingError(missing_details)
