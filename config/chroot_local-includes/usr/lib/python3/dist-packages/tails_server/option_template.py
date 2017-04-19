import abc
import logging
import yaml

from tails_server import util

# Only required for type hints
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from tails_server.service_template import TailsService


PERSISTENT_TORRC = "/usr/share/tor/tor-service-defaults-torrc"
CONFIG_DIR_PREFIX = "config_"


class OptionNotFoundError(Exception):
    pass


class TailsServiceOption(metaclass=abc.ABCMeta):
    @property
    @abc.abstractmethod
    def name(self):
        """The name of the option, as used in the CLI and the stored options file"""
        pass

    @property
    def name_in_gui(self):
        """The name of the option as displayed in the GUI"""
        return self.name.replace("-", " ").title()

    @property
    @abc.abstractmethod
    def description(self):
        """A short description of the option that will be displayed in the GUI"""
        pass

    @property
    @abc.abstractmethod
    def type(self):
        """The option's type. This will determine which widgets are used for this option in the
        GUI. Defaults to str"""
        return str

    @property
    @abc.abstractmethod
    def default(self):
        """The default value of this option"""
        pass

    @property
    def value(self):
        """The option's value. Setting this to a different value will automatically trigger
        on_value_changed, which will store and apply the value"""
        return self._value

    @value.setter
    def value(self, value):
        if self.type == bool and type(value) != bool:
            choices = ["true", "false"]
            if value.lower() not in choices:
                self.service.arg_parser.error("Invalid value %r for option %r. Possible values: %r"
                                              % (value, self.name, choices))
            value = value.lower() == "true"

        if self._value != value:
            self._value = value
            self.on_value_changed()

    @property
    def info_attributes(self):
        return {
            "name": self.name,
            "description": self.description,
            "type": self.type,
            "default": self.default,
            "value": self.value,
        }

    # options with the same group are grouped together in the GUI
    group = str()

    # the value of a masked option will not be displayed in cleartext in the GUI and CLI
    masked = False

    # read-only options can not be edited
    read_only = False

    # the option value will be reloaded in the GUI after the service was successfully started (
    # i.e. systemd unit started, the onion service started, and the descriptor was uploaded).
    # This is useful for options which change when the service starts.
    reload_after_service_started = False

    def __init__(self, service: "TailsService"):
        self.service = service        
        self.reload()

    def reload(self):
        try:
            self._value = self.load()
        except OptionNotFoundError as e:
            logging.debug(str(e))
            self._value = self.default
            self.store()

    def load(self):
        """Load the option's value from the option file. Create the option file if it doesn't exist.
        If this option has any other stable representation (e.g. in a config file), this function
        should be overridden and load this other representation instead"""
        try:
            return self.do_load()
        except (FileNotFoundError, ValueError, TypeError):
            self.service.create_options_file()
            return self.do_load()

    def do_load(self):
        logging.debug("Loading option %r", self.name)
        with util.open_locked(self.service.options_file) as f:
            options = yaml.load(f)
            logging.debug("options: %r", options)
        if self.name not in options:
            raise OptionNotFoundError("Could not find option %r in %r" %
                                      (self.name, self.service.options_file))
        value = options[self.name]
        return self.type(value)

    def store(self):
        """Store the option's value in the option file. If this option has any other stable
        representation (e.g. if it modifies a config file), this function should be overridden
        and replace this other representation instead."""
        try:
            return self.do_store()
        except (FileNotFoundError, ValueError, TypeError):
            self.service.create_options_file()
            return self.do_store()

    def do_store(self):
        logging.debug("Storing option %r", self.name)
        with util.open_locked(self.service.options_file) as f:
            options = yaml.load(f)
        options[self.name] = self.value
        with util.open_locked(self.service.options_file, 'w+') as f:
            yaml.dump(options, f, default_flow_style=False)

    def on_value_changed(self):
        logging.debug("Option %r value changed to %r", self.name, self.value)
        self.store()
        self.apply()

    def apply(self):
        """This function should be overridden if the option will not automatically apply after
        store() is called and the service is restarted (if the option is stored in a config file,
        it will usually be applied automatically by restarting the service).

        By default, this is NOT called during option initialization, because some options should
        not be applied before actually set (e.g. allow-lan and allow-localhost, for which
        applying the default value would result in removing non-existent iptables rules).
        If you want to apply the default value, call self.apply() in __init__()."""
        logging.debug("Applying option %s", self.name)

    def clean_up(self):
        """This function should be overridden if something needs to be cleaned up for this option
        when the service is uninstalled."""
        logging.debug("Cleaning option %s", self.name)

    def __str__(self):
        return "%s: %s" % (self.name, self.value)
