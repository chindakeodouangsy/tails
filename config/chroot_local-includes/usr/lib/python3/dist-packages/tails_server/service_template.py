import os
import shutil
import abc
import sh
import logging
from collections import OrderedDict
import inspect

import yaml
import yaml.resolver
import apt
import stem.control

from tails_server import _
from tails_server import tor_util
from tails_server import util
from tails_server import argument_parser

from tails_server.options.virtual_port import VirtualPort
from tails_server.options.persistence import PersistenceOption
from tails_server.options.autostart import AutoStartOption
from tails_server.options.allow_localhost import AllowLocalhostOption
from tails_server.options.allow_lan import AllowLanOption

from tails_server.exceptions import TorIsNotRunningError
from tails_server.exceptions import UnknownOptionError
from tails_server.exceptions import ServiceNotInstalledError
from tails_server.exceptions import ServiceAlreadyInstalledError
from tails_server.exceptions import ServiceAlreadyEnabledError
from tails_server.exceptions import OptionNotInitializedError
from tails_server.exceptions import AlreadyMountedError

from tails_server.config import HS_DIR, TOR_USER, TAILS_SERVER_USER, STATE_DIR, \
    OPTIONS_FILE_NAME, PERSISTENCE_CONFIG_NAME, PERSISTENCE_DIR, INSTALLED_FILE_PATH

# Only required for type hints
from typing import TYPE_CHECKING, List, Union
if TYPE_CHECKING:
    from tails_server.option_template import TailsServiceOption


class PersistenceRecord(object):
    def __init__(self, target_path, persistence_path):
        self.target_path = target_path
        self.persistence_path = persistence_path


class LazyOptionDict(OrderedDict):
    """Expects classes as its values. When a value is retrieved, it returns an instance of the
    respective class.
    This prevents all of the options being instantiated when Tails Server is started,
    thus reducing waiting time for the user.

    XXX: Evaluate how much we really gain from this vs. the complexity it adds.
         Update: Tried to replace this with a normal OrderedDict, but this caused circular
         dependencies between options, which I could not resolve. So maybe it's easier to just
         keep this."""

    def __init__(self, service: "TailsService", *args, **kwargs):
        self.service = service
        super().__init__(*args, **kwargs)

    def __getitem__(self, key) -> "TailsServiceOption":
        item = super(LazyOptionDict, self).__getitem__(key)
        if inspect.isclass(item):
            logging.debug("Instantiating %r", item)
            self.__setitem__(key, item(self.service))
        return super(LazyOptionDict, self).__getitem__(key)

    def values(self) -> List["TailsServiceOption"]:
        """Returns all stored values, which automatically instantiates them.
        The new dictionary view object returned by dict.values() in Python 3.5 does not call
        __getitem__, so we have to override dict.values() here."""
        return [self[key] for key in self.keys()]

    def get_items(self) -> List[Union[type, "TailsServiceOption"]]:
        """Get the stored values *without* instantiating them"""
        return [super(LazyOptionDict, self).__getitem__(key) for key in self.keys()]

    def get_instantiated(self) -> List["TailsServiceOption"]:
        """Returns only the already instantiated values"""
        items = self.get_items()
        return [item for item in items if not inspect.isclass(item)]


class TailsService(metaclass=abc.ABCMeta):

    connection_info_format = "1.0"

    arg_parser = argument_parser.ServiceParser()

    @property
    @abc.abstractmethod
    def name(self):
        """The name of the service, as used in the CLI.
        This should be the same as the basename of the service's script."""
        return str()

    @property
    def name_in_gui(self):
        """The name of the service, as displayed in the GUI."""
        return self.name.replace("-", " ").replace("_", " ").title()

    @property
    @abc.abstractmethod
    def description(self):
        """A short description of the service, which will be displayed in the GUI."""
        return str()

    @property
    @abc.abstractmethod
    def client_application(self):
        """The name of the application which can connect to this service."""
        return str()

    @property
    def client_application_in_gui(self):
        """The name of the application which can connect to this service, as displayed in the
        GUI."""
        return self.client_application.replace("-", " ").replace("_", " ").title()

    @property
    @abc.abstractmethod
    def packages(self):
        """Packages needed by this service.
        These will be installed when the service is installed."""
        return list()

    @property
    def publish_hs_before_starting(self):
        """Whether to publish the hidden service before starting the service.
        This is useful for services whose configuration must include the hidden
        service address."""
        return False

    @property
    @abc.abstractmethod
    def systemd_service(self):
        """The name of the service's systemd service"""
        return "%s.service" % self.name

    @property
    @abc.abstractmethod
    def default_target_port(self):
        """The default value of the service's target port (i.e. the port opened by the service on
        localhost) if the user does not specify a custom target port"""
        return int()

    @property
    def target_port(self):
        """The port opened by the service on localhost which should be forwarded via Tor"""
        if "target-port" in self.options_dict:
            return self.options_dict["target-port"].value
        return self.default_target_port

    @property
    def default_virtual_port(self):
        """The default value of the service's virtual port (i.e. the port exposed via the onion
        service) if the user does not specify a custom virtual port"""
        return self.default_target_port

    @property
    def virtual_port(self):
        """The port exposed via the onion service, i.e. the port clients have to use to connect to
        the service"""
        if "virtual-port" in self.options_dict:
            return self.options_dict["virtual-port"].value
        return self.default_virtual_port

    @property
    def connection_info(self):
        """A summary of all information necessary to connect to the service"""
        if not self.address:
            return None

        s = str()
        s += _("Application: %s (format: %s)\n") % (self.client_application_in_gui,
                                                   self.connection_info_format)
        s += _("Address: %s:%s") % (self.address, self.virtual_port)
        return s

    @property
    def connection_info_in_gui(self):
        """The connection as it should be displayed in the GUI"""
        return self.connection_info

    @property
    @abc.abstractmethod
    def icon_name(self):
        """Name of the icon to use for this service in the GUI"""
        return self.name

    documentation = str()
    persistent_paths = list()

    options = [
        VirtualPort,
        PersistenceOption,
        AutoStartOption,
        AllowLocalhostOption,
        AllowLanOption,
    ]

    _options_dict = None

    @property
    def options_dict(self) -> LazyOptionDict:
        """A LazyOptionDict mapping the names of this service's options to the options' classes.
        The LazyOptionDict automatically instantiates an option the first time it is accessed,
        so then the dict maps the option's name to the option object.
        The reasoning for this is that instantiating an option usually requires disk reads and
        therefore is very slow, so we don't want to instantiate all the options when the GUI
        starts, because this would slow the start of the GUI down a lot. Instead we only
        instantiate the options when they are actually needed."""
        if not self._options_dict:
            self._options_dict = LazyOptionDict(
                self, [(option.name, option) for option in self.options])
        return self._options_dict

    @property
    def is_installed(self):
        installed_services = util.get_installed_services()
        return self.name in installed_services

    @is_installed.setter
    def is_installed(self, value):
        installed_services = util.get_installed_services()
        if value:
            installed_services |= {self.name}
        else:
            installed_services -= {self.name}
        with util.open_locked(INSTALLED_FILE_PATH, "w+") as f:
            f.write(yaml.dump(list(installed_services), default_flow_style=False))

    @property
    def is_running(self):
        try:
            sh.systemctl("is-active", self.systemd_service)
        except sh.ErrorReturnCode_3:  # inactive
            return False
        return True

    @property
    def is_persistent(self):
        if "persistence" not in self.options_dict:
            raise OptionNotInitializedError(option="persistence")
        return self.options_dict["persistence"].value

    @property
    def is_published(self):
        if not self.address:
            return False
        return tor_util.is_published(self.address)

    @property
    def address(self):
        """
        The hidden service hostname aka onion address of this service.
        :return: onion address
        """
        try:
            with util.open_locked(self.hs_hostname_file, 'r') as f:
                return f.read().split()[0].strip()
        except FileNotFoundError:
            return None

    @property
    def info_attributes(self):
        attributes = OrderedDict([
            ("description", self.description),
            ("installed", self.is_installed),
        ])
        if self.is_installed:
            attributes.update(OrderedDict([
                ("running", self.is_running),
                ("published", self.is_running),
                ("address", self.address),
                ("local-port", self.target_port),
                ("remote-port", self.virtual_port),
                ("persistent-paths", self.persistent_paths),
                ("options", OrderedDict([(option.name, option.value) for option in
                                         self.options_dict.values()])),
            ]))
        return attributes

    @property
    def info_attributes_all(self):
        attributes = OrderedDict()
        attributes["name"] = self.name
        attributes["name-in-gui"] = self.name_in_gui
        attributes.update(self.info_attributes)
        attributes["hidden-service-dir"] = self.hs_dir
        attributes["packages"] = self.packages
        attributes["systemd-service"] = self.systemd_service
        attributes["icon-name"] = self.icon_name
        attributes["options"] = [option.info_attributes for option in self.options_dict.values()]
        return attributes

    @staticmethod
    def print_yaml(*args, **kwargs):
        def _dict_representer(dumper, data):
            return dumper.represent_mapping(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
                                            data.items())

        class OrderedDictDumper(yaml.Dumper):
            def ignore_aliases(self, data):
                return True

        OrderedDictDumper.add_representer(OrderedDict, _dict_representer)
        print(yaml.dump(*args, Dumper=OrderedDictDumper, default_flow_style=False, **kwargs), end="")

    @property
    def default_persistence_records(self):
        return [
            PersistenceRecord(
                target_path=self.hs_dir,
                persistence_path=os.path.join(self.persistence_dir, "hidden_service")
            ),
            PersistenceRecord(
                target_path=self.options_file,
                persistence_path=os.path.join(self.persistence_dir, OPTIONS_FILE_NAME)
            )
        ]

    @property
    def persistence_records(self) -> List[PersistenceRecord]:
        persistence_records = self.default_persistence_records
        for persistent_path in self.persistent_paths:
            path = os.path.normpath(persistent_path)
            persistence_records.append(
                PersistenceRecord(
                    target_path=path,
                    persistence_path=os.path.join(self.persistence_dir, os.path.basename(path))
                )
            )

        return persistence_records

    def __init__(self):
        self.state_dir = os.path.join(STATE_DIR, self.name)
        self.create_state_dir()
        self.hs_dir = os.path.join(HS_DIR, self.name)
        self.hs_hostname_file = os.path.join(self.hs_dir, "hostname")
        self.hs_private_key_file = os.path.join(self.hs_dir, "private_key")
        self.options_file = os.path.join(self.state_dir, OPTIONS_FILE_NAME)
        self.persistence_config = os.path.join(self.state_dir, PERSISTENCE_CONFIG_NAME)
        self.persistence_dir = os.path.join(PERSISTENCE_DIR, self.name)
        self._target_port = self.default_target_port
        self._virtual_port = self.default_virtual_port

    def get_status(self):
        return {"installed": self.is_installed,
                "running": self.is_running,
                "published": self.is_published}

    def print_status(self):
        status = self.get_status()
        self.print_yaml(status)

    def print_info(self, detailed=False):
        logging.debug("Getting attributes")
        attributes = self.info_attributes_all if detailed else self.info_attributes
        logging.debug("Dumping attributes")
        self.print_yaml(attributes)

    def enable(self):
        if not self.is_installed:
            raise ServiceNotInstalledError("Service %r is not installed" % self.name)

        if self.is_running and self.is_published:
            raise ServiceAlreadyEnabledError("Service %r is already enabled" % self.name)
        logging.info("Enabling service %r" % self.name)

        if not tor_util.tor_has_bootstrapped():
            raise TorIsNotRunningError()

        if self.publish_hs_before_starting:
            if not self.is_published:
                self.create_hidden_service()
            if not self.is_running:
                self.start()
        else:
            if not self.is_running:
                self.start()
            if not self.is_published:
                self.create_hidden_service()

    def install(self):
        def update_package_lists():
            logging.info("Updating package lists")
            cache.update()

        with util.prepare_apt_installation():
            if self.is_installed:
                raise ServiceAlreadyInstalledError("Service %r is already installed" % self.name)

            logging.info("Installing packages: " + ", ".join("%r" % p for p in self.packages))

            cache = apt.Cache()
            logging.debug("Checking if packages are in cache")
            if any([package not in cache for package in self.packages]):
                update_package_lists()

            logging.debug("Running apt-get install")
            sh.apt_get("install", "-y", "-o", 'Dpkg::Options::=--force-confold',
                       "--no-install-recommends", self.packages)

        logging.debug("%r installed", self.name)
        self.is_installed = True
        self.configure()
        logging.debug("%r configured", self.name)

    def configure(self):
        """Initial configuration after installing the service"""
        pass

    def install_using_apt_module(self):
        # There seems to be no way to automatically keep old config on conflicts with the apt module
        cache = apt.Cache()
        for package in self.packages:
            cache[package].mark_install()
        with util.prepare_apt_installation():
            cache.commit()
        logging.info("Service %r installed", self.name)

    def uninstall(self):
        if not self.is_installed:
            raise ServiceNotInstalledError("Service %r is not installed" % self.name)

        if self.is_running:
            self.disable()
        for option in self.options_dict.get_instantiated():
            option.clean_up()
        self.remove_options_file()
        self.remove_state_dir()
        self.remove_hs_dir()
        self.remove_persistence_dir()
        self.is_installed = False
        logging.info("Service %r uninstalled", self.name)

    def restore(self):
        logging.info("Restoring service %r", self.name)
        self.install()
        self.mount_persistent_files()
        for option in self.options_dict:
            if option != "persistence":
                self.options_dict[option].apply()

    def mount_persistent_files(self):
        logging.info("Bind-mounting persistent files of service %r", self.name)
        for record in self.persistence_records:
            logging.debug("Bind-mounting %r to %r", record.persistence_path, record.target_path)
            if util.is_mounted(record.target_path):
                raise AlreadyMountedError("%r is already mounted" % record.target_path)
            self.ensure_target_exists(record)
            sh.mount("--bind", record.persistence_path, record.target_path)

    def unmount_persistent_files(self):
        logging.info("Unmounting persistent files of service %r", self.name)
        for record in self.persistence_records:
            logging.debug("Unmounting %r", record.target_path)
            sh.umount(record.target_path)
            self.remove_target(record)

    @staticmethod
    def ensure_target_exists(persistence_record):
        if os.path.exists(persistence_record.target_path):
            return
        if os.path.isdir(persistence_record.persistence_path):
            sh.mkdir(persistence_record.target_path)
        else:
            sh.touch(persistence_record.target_path)

    @staticmethod
    def remove_target(persistence_record):
        if os.path.isdir(persistence_record.persistence_path):
            sh.rmdir(persistence_record.target_path)
        else:
            sh.rm(persistence_record.target_path)

    def create_state_dir(self):
        if not os.path.exists(self.state_dir):
            logging.debug("Creating state directory %r", self.state_dir)
            os.mkdir(self.state_dir)
        shutil.chown(self.state_dir, user=TAILS_SERVER_USER, group=TAILS_SERVER_USER)
        os.chmod(self.state_dir, 0o770)

    def remove_state_dir(self):
        logging.debug("Removing state directory %r", self.state_dir)
        shutil.rmtree(self.state_dir)

    def create_options_file(self):
        logging.debug("Creating empty options file for %r", self.name)
        with util.open_locked(self.options_file, "w+") as f:
            yaml.dump(dict(), f)

    def remove_options_file(self):
        logging.info("Removing options file %r", self.options_file)
        try:
            os.remove(self.options_file)
        except FileNotFoundError:
            logging.error("Couldn't remove options file", exc_info=True)

    def create_hs_dir(self):
        logging.info("Creating hidden service directory %r", self.hs_dir)
        try:
            os.mkdir(self.hs_dir)
            os.chmod(self.hs_dir, 0o700)
        except FileExistsError:
            # The UID of debian-tor might change between Tails releases (it did before)
            # This would cause existing persistent directories to have wrong UIDs,
            # so we reset them here
            for dirpath, _, filenames in os.walk(self.hs_dir):
                for filename in filenames:
                    shutil.chown(os.path.join(dirpath, filename), TOR_USER, TOR_USER)
        shutil.chown(self.hs_dir, TOR_USER, TOR_USER)

    def remove_hs_dir(self):
        if os.path.exists(self.hs_dir):
            logging.info("Removing HS directory %r", self.hs_dir)
            shutil.rmtree(self.hs_dir)

    def create_persistence_dir(self):
        logging.info("Creating persistence directory %r", self.persistence_dir)
        sh.install("-m", 755, "-d", self.persistence_dir)

    def remove_persistence_dir(self):
        if os.path.exists(self.persistence_dir):
            logging.info("Removing persistence directory %r", self.persistence_dir)
            shutil.rmtree(self.persistence_dir)

    def start(self):
        logging.info("Starting service %r. Command: `systemctl start %s`", self.name, self.systemd_service)
        sh.systemctl("start", self.systemd_service)
        # XXX: Listen for JobRemoved events to check if the service was started successfully

    def disable(self):
        self.stop()
        self.remove_hidden_service()

    def stop(self):
        logging.info("Stopping service %r", self.name)
        sh.systemctl("stop", self.systemd_service)

    def get_option(self, option_name):
        if not self.is_installed:
            raise ServiceNotInstalledError("Service %r is not installed" % self.name)

        try:
            option = self.options_dict[option_name]
        except KeyError:
            raise UnknownOptionError("Service %r has no option %r" % (self.name, option_name))

        self.print_yaml({option.name: option.value})

    def set_option(self, option_name, value):
        if not self.is_installed:
            raise ServiceNotInstalledError("Service %r is not installed" % self.name)

        try:
            option = self.options_dict[option_name]
        except KeyError:
            raise UnknownOptionError("Service %r has no option %r" % (self.name, option_name))

        option.value = value
        logging.debug("Option %r set to %r", option_name, value)
        return

    def reset_option(self, option_name):
        if not self.is_installed:
            raise ServiceNotInstalledError("Service %r is not installed" % self.name)

        try:
            option = self.options_dict[option_name]
        except KeyError:
            raise UnknownOptionError("Service %r has no option %r" % (self.name, option_name))

        option.value = option.default
        option.apply()
        logging.debug("Option %r reset to %r", option_name, option.value)
        return

    def create_hidden_service(self):
        """Creating hidden service and setting address and hs_private_key accordingly"""
        logging.info("Creating hidden service")
        if not self.is_running and not self.publish_hs_before_starting:
            logging.warning("Refusing to create hidden service of not-running service %r",
                            self.name)
            return

        self.create_hs_dir()

        try:
            key_type = "RSA1024"
            with util.open_locked(self.hs_private_key_file, 'r') as f:
                key_content = f.read()
        except FileNotFoundError:
            key_type = "NEW"
            key_content = "RSA1024"

        controller = stem.control.Controller.from_socket_file()
        controller.authenticate()
        # We have to use create_ephemeral_hidden_service() here instead of create_hidden_service(),
        # because the latter needs to access the filesystem, which is prevented by the Tor sandbox
        # see https://github.com/micahflee/onionshare/issues/179
        response = controller.create_ephemeral_hidden_service(
            ports={self.virtual_port: self.target_port},
            key_type=key_type,
            key_content=key_content,
            discard_key=False,
            detached=True,
            await_publication=True
        )

        if response.service_id:
            self.set_onion_address(response.service_id)
        if response.private_key:
            self.set_hs_private_key(response.private_key)

    def set_onion_address(self, address: str):
        with util.open_locked(self.hs_hostname_file, 'w+') as f:
            f.write(address + ".onion")

    def set_hs_private_key(self, key):
        with util.open_locked(self.hs_private_key_file, 'w+') as f:
            f.write(key)

    def remove_hidden_service(self):
        logging.info("Removing hidden service")
        if not self.address:
            logging.warning("Can't remove onion address of service %r: Address is not set",
                            self.name)
            return

        controller = stem.control.Controller.from_socket_file()
        controller.authenticate()
        controller.remove_ephemeral_hidden_service(self.address.replace(".onion", ""))

    def remove_onion_address(self):
        os.remove(self.hs_hostname_file)
        os.remove(self.hs_private_key_file)
