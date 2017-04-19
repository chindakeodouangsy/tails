import os
import random
import string
import sh

from tails_server import _
from tails_server import util
from tails_server import file_util
from tails_server import option_util
from tails_server import service_template
from tails_server import option_template
from tails_server.options.virtual_port import VirtualPort
from tails_server.options.persistence import PersistenceOption
from tails_server.options.autostart import AutoStartOption
from tails_server.options.allow_localhost import AllowLocalhostOption
from tails_server.options.allow_lan import AllowLanOption

CONFIG_FILE = "/etc/xdg/infinoted.conf"
DATA_DIR = "/var/lib/infinoted"
DOCS_DIR = os.path.join(DATA_DIR, "docs")
LOG_FILE = os.path.join(DATA_DIR, "infinoted.log")


class ServerPasswordOption(option_template.TailsServiceOption):
    DEFAULT_LENGTH = 20
    name = "server-password"
    name_in_gui = "Password"
    description = "Password required to connect to service"
    type = str
    group = "connection"
    masked = True

    @property
    def default(self):
        return ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in
                       range(self.DEFAULT_LENGTH))

    def store(self):
        file_util.delete_lines_starting_with(CONFIG_FILE, "password=")
        if self.value:
            file_util.insert_to_section(CONFIG_FILE, "infinoted", "password=%s\n" % self.value)

    def load(self):
        if not os.path.exists(CONFIG_FILE):
            raise FileNotFoundError("File %r is required but could not be found" % CONFIG_FILE)

        value = option_util.get_option(CONFIG_FILE, "password=")
        return value


class AutoSaveInterval(option_template.TailsServiceOption):
    name = "autosave-interval"
    name_in_gui = "Autosave Interval (Sec)"
    description = "Interval in seconds to automatically save all open documents"
    default = 30
    type = int
    group = "advanced"

    def store(self):
        file_util.delete_section(CONFIG_FILE, "autosave")
        file_util.append_to_file(CONFIG_FILE, "[autosave]\n")
        file_util.append_to_file(CONFIG_FILE, "interval=%s\n" % self.value)

    def load(self):
        if not os.path.exists(CONFIG_FILE):
            raise FileNotFoundError("File %r is required but could not be found" % CONFIG_FILE)

        value = option_util.get_option(CONFIG_FILE, "interval=")
        return value


class GobbyServer(service_template.TailsService):
    name = "gobby"
    description = _("A collaborative text editing service")
    systemd_service = "gobby-server.service"
    client_application = "gobby"
    packages = ["infinoted"]
    default_target_port = 6523
    documentation = "file:///usr/share/doc/tails/website/doc/tails_server/gobby.en.html"
    persistent_paths = [CONFIG_FILE, DATA_DIR]
    icon_name = "gobby-0.5"
    group_order = ["connection", "generic-checkbox", "advanced"]

    options = [
        VirtualPort,
        ServerPasswordOption,
        PersistenceOption,
        AutoStartOption,
        AllowLocalhostOption,
        AllowLanOption,
        AutoSaveInterval,
    ]

    def configure(self):
        self.set_option("allow-localhost", True)

        with util.open_locked(CONFIG_FILE, "w+") as f:
            f.write("[infinoted]\n")
            f.write("root-directory=%s\n" % DATA_DIR)
            f.write("log-file=%s\n" % LOG_FILE)
            f.write("security-policy=no-tls\n")

        sh.chown("root:infinoted", CONFIG_FILE)
        sh.chmod("640", CONFIG_FILE)

        if not os.path.isdir(DATA_DIR):
            os.mkdir(DATA_DIR, mode=0o700)

        super().configure()

    # def start(self):
    #     logging.info("Starting gobby server infinoted")
    #     sh.infinoted("-d")
    #
    # def stop(self):
    #     logging.info("Stopping gobby server infinoted")
    #     sh.infinoted("-D")

    @property
    def connection_info(self):
        if not self.address:
            return None

        s = str()
        s += _("Application: %s (format: %s)\n") % (self.client_application_in_gui,
                                                    self.connection_info_format)
        s += _("Address: %s\n") % self.address
        s += _("Port: %s\n") % self.virtual_port
        s += _("Password: %s") % self.options_dict["server-password"].value
        return s


service_class = GobbyServer
