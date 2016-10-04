import os
import abc
import shutil
import sh
import logging
import yaml

from tails_server import _
from tails_server import file_util
from tails_server.config import TOR_DIR, TOR_USER, TOR_SERVICE, TORRC, PERSISTENCE_DIR, \
    PERSISTENCE_DIR_NAME, PERSISTENCE_CONFIG

PERSISTENT_TORRC = "/usr/share/tor/tor-service-defaults-torrc"
CONFIG_DIR_PREFIX = "config_"


class AlreadyPersistentError(Exception):
    pass


class NotPersistentError(Exception):
    pass


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
        logging.debug("New value: %r, old value: %r", self._value, value)
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
            logging.debug("OptionNotFoundError: " + str(e))
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
        logging.debug("Storing option %r", self.name)
        with open(self.service.options_file) as f:
            options = yaml.load(f)
        options[self.name] = self.value
        with open(self.service.options_file, 'w+') as f:
            yaml.dump(options, f, default_flow_style=False)

    def on_value_changed(self):
        logging.debug("Option %r set to %r", self.name, self.value)
        self.store()
        self.apply()

    def apply(self):
        """This function should be overridden if the option will not automatically apply after
        store() is called and the service is restarted (if the option is stored in a config file,
        it will usually be applied automatically by restarting the service)."""
        logging.debug("Applying option %s", self.name)

    def clean(self):
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

    def clean(self):
        super().clean()
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

    def clean(self):
        super().clean()
        if self.value:
            self.reject_lan_connections()


class AutoStartOption(TailsServiceOption):
    name = "autostart"
    name_in_gui = _("Autostart")
    description = _("Start service automatically after booting Tails")
    type = bool
    default = False
    group = "generic-checkbox"

    def apply(self):
        super().apply()
        # if self.value:
        #     self.service.add_to_additional_software()
        # else:
        #     self.service.remove_from_additional_software()

    def clean(self):
        super().clean()
        if self.value:
            self.service.remove_from_additional_software()


class PersistenceOption(TailsServiceOption):
    PERSISTENT_HS_DIR = "hidden_service"
    PERSISTENT_OPTIONS_FILE = "options"

    name = "persistence"
    description = _("Store service configuration and data on the persistent volume")
    type = bool
    default = False
    group = "generic-checkbox"

    @property
    def persistence_dir(self):
        return os.path.join(PERSISTENCE_DIR, self.service.name)

    def apply(self):
        super().apply()
        # if self.value:
        #     self.make_persistent()
        # else:
        #     self.remove_persistence()

    def clean(self):
        super().clean()
        if self.value:
            self.remove_persistence()

    def make_persistent(self):
        self.create_persistence_dirs()
        self.service.create_hs_dir()
        self.make_path_persistent(self.service.hs_dir, persistence_name=self.PERSISTENT_HS_DIR)
        self.make_path_persistent(self.service.options_file,
                                  persistence_name=self.PERSISTENT_OPTIONS_FILE)
        self.make_config_files_persistent()

    def create_persistence_dirs(self):
        if not os.path.exists(PERSISTENCE_DIR):
            os.mkdir(PERSISTENCE_DIR)
            os.chmod(PERSISTENCE_DIR, 0o755)
        if not os.path.exists(self.persistence_dir):
            os.mkdir(self.persistence_dir)
            os.chmod(self.persistence_dir, 0o755)

    def make_path_persistent(self, path, persistence_name=None):
        is_dir = os.path.isdir(path)
        dest = os.path.join(self.persistence_dir, persistence_name)
        if not persistence_name:
            persistence_name = os.path.basename(path)
        self.add_to_persistence_config(path, persistence_name)
        self.move(path, dest)
        if is_dir:
            self.create_empty_dir(path)
        else:
            self.create_empty_file(path)
        sh.mount("--bind", dest, path)

    @staticmethod
    def move(src, dest):
        if os.path.isdir(src):
            shutil.copytree(src, dest)
            shutil.rmtree(src)
        else:
            shutil.move(src, dest)
        logging.debug("Moved %r to %r", src, dest)

    @staticmethod
    def create_empty_file(path):
        open(path, 'w+').close()

    @staticmethod
    def create_empty_dir(path):
        os.mkdir(path)

    def add_to_persistence_config(self, path, persistence_name):
        line = "%s source=%s\n" % (
            path, os.path.join(PERSISTENCE_DIR_NAME, self.service.name, persistence_name))
        self.add_line_to_persistence_config(line)

    def add_line_to_persistence_config(self, line):
        written = file_util.append_line_if_not_present(PERSISTENCE_CONFIG, line)
        if not written:
            raise AlreadyPersistentError(
                "Service %r seems to already have an entry in persistence config file %r" %
                (self.service.name, PERSISTENCE_CONFIG))
        logging.debug("Added line to persistence.config: %r", line)

    def make_config_files_persistent(self):
        for path in self.service.persistent_paths:
            self.make_path_persistent(path)

    def remove_persistence(self):
        self.remove_from_persistence(self.service.hs_dir, self.PERSISTENT_HS_DIR)
        self.remove_from_persistence(self.service.options_file,
                                     persistence_name=self.PERSISTENT_OPTIONS_FILE)
        self.remove_config_files_from_persistence()

    def remove_from_persistence(self, path, persistence_name=None):
        if not persistence_name:
            persistence_name = os.path.basename(path)
        try:
            self.remove_from_persistence_config(path, persistence_name)
        except NotPersistentError as e:
            logging.error(e)
        self.remove_from_persistence_volume(path, persistence_name)

    def remove_from_persistence_volume(self, path, persistence_name):
        try:
            sh.umount(path)
        except sh.ErrorReturnCode_32 as e:
            logging.error(e)

        try:
            if os.path.isdir(path):
                os.rmdir(path)
            else:
                os.remove(path)
        except FileNotFoundError as e:
            logging.error(e)

        try:
            # shutil.move doesn't preserve ownership, so we use sh.mv here instead
            sh.mv(os.path.join(self.persistence_dir, persistence_name), path)
        except FileNotFoundError as e:
            logging.error(e)

    def remove_from_persistence_config(self, path, persistence_name):
        line = "%s source=%s\n" % (
            path, os.path.join(PERSISTENCE_DIR_NAME, self.service.name, persistence_name))
        self.remove_line_from_persistence_config(line)

    def remove_line_from_persistence_config(self, line):
        logging.debug("Removing line %r from persistence.conf", line)
        removed = file_util.remove_line_if_present(PERSISTENCE_CONFIG, line)
        if not removed:
            raise NotPersistentError(
                "Service %r seems to have no entry in persistence config file %r. "
                "Line not found: %r" % (self.service.name, PERSISTENCE_CONFIG, line))

    def remove_config_files_from_persistence(self):
        for path in self.service.persistent_paths:
            self.remove_from_persistence(path)
