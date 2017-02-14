import os
import abc
import sh
import logging
import yaml

from tails_server import _

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

    group = None
    masked = False

    def __init__(self, service):
        self.service = service        
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
        with open(self.service.options_file) as f:
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
        with open(self.service.options_file) as f:
            options = yaml.load(f)
        options[self.name] = self.value
        with open(self.service.options_file, 'w+') as f:
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


class VirtualPort(TailsServiceOption):
    name = "virtual-port"
    name_in_gui = _("Port")
    description = _("Port opened on the Tor network")
    type = int
    group = "connection"

    @property
    def default(self):
        return self.service.default_virtual_port


class AllowLocalhostOption(TailsServiceOption):
    name = "allow-localhost"
    name_in_gui = _("Allow localhost")
    description = _("Allow connections from localhost")
    type = bool
    default = False
    group = "generic-checkbox"

    @property
    def rule(self):
        return ("OUTPUT", "--out-interface", "lo", "--protocol", "tcp", "--dport",
                self.service.target_port, "--jump", "ACCEPT")

    def store(self):
        super().store()
        if self.value:
            self.accept_localhost_connections()
        else:
            self.reject_localhost_connections()

    def accept_localhost_connections(self):
        sh.iptables("-I", *self.rule)

    def reject_localhost_connections(self):
        sh.iptables("-D", *self.rule)

    def load(self):
        return self.is_allowed()

    def is_allowed(self):
        try:
            sh.iptables("-C", *self.rule)
            return True
        except sh.ErrorReturnCode_1:
            return False

    def clean_up(self):
        super().clean_up()
        if self.value:
            self.reject_localhost_connections()


class AllowLanOption(TailsServiceOption):
    name = "allow-lan"
    name_in_gui = _("Allow LAN")
    description = _("Allow connections from the local network")
    type = bool
    default = False
    group = "generic-checkbox"

    @property
    def rules(self):
        return [("INPUT", "--source", subnet, "--protocol", "tcp", "--dport",
                self.service.target_port, "--jump", "ACCEPT")
                for subnet in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")]

    def store(self):
        super().store()
        if self.value:
            self.accept_lan_connections()
        else:
            self.reject_lan_connections()

    def accept_lan_connections(self):
        for rule in self.rules:
            sh.iptables("-I", *rule)

    def reject_lan_connections(self):
        for rule in self.rules:
            sh.iptables("-D", *rule)

    def load(self):
        return self.is_allowed()

    def is_allowed(self):
        return all(self.is_active(rule) for rule in self.rules)

    @staticmethod
    def is_active(rule):
        try:
            sh.iptables("-C", *rule)
            return True
        except sh.ErrorReturnCode_1:
            return False

    def clean_up(self):
        super().clean_up()
        if self.value:
            self.reject_lan_connections()


class AutoStartOption(TailsServiceOption):
    name = "autostart"
    name_in_gui = _("Autostart")
    description = _("Start service automatically after booting Tails")
    type = bool
    default = False
    group = "generic-checkbox"


class PersistenceOption(TailsServiceOption):
    name = "persistence"
    description = _("Store service configuration and data on the persistent volume")
    type = bool
    default = False
    group = "generic-checkbox"

    def apply(self):
        super().apply()
        if self.value:
            self.make_persistent()
        else:
            self.remove_persistence()

    def clean_up(self):
        super().clean_up()
        if self.value:
            self.remove_persistence()

    def make_persistent(self):
        logging.info("Making %r persistent", self.service.name)
        self.service.create_persistence_dir()
        self.service.create_hs_dir()
        for record in self.service.persistence_records:
            self.move(record.target_path, record.persistence_path)
        self.service.mount_persistent_files()

    def remove_persistence(self):
        logging.info("Removing persistence of %r", self.service.name)
        try:
            self.service.unmount_persistent_files()
        except sh.ErrorReturnCode_32:
            logging.error("Error while unmounting persistent files", exc_info=True)

        try:
            for record in self.service.persistence_records:
                self.move(record.persistence_path, record.target_path)
        except (sh.ErrorReturnCode_1, FileExistsError):
            logging.error("Error while moving persistent files", exc_info=True)

    @staticmethod
    def move(src, dest):
        logging.debug("Moving %r to %r", src, dest)
        if os.path.exists(dest):
            raise FileExistsError("Couldn't move %r to %r, destination %r already exists" %
                                  (src, dest, dest))

        sh.mv(src, dest)
