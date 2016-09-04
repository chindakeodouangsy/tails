#!/usr/bin/env python3

import string
import random
import sqlite3
import OpenSSL.crypto

from tails_server import _
from tails_server import file_util
from tails_server import option_util
from tails_server import service_template
from tails_server import service_option_template

CONFIG_FILE = "/etc/mumble-server.ini"


class WelcomeMessageOption(service_option_template.TailsServiceOption):
    name = "welcome-message"
    name_in_gui = _("Welcome Message")
    description = _("Welcome message sent to clients when they connect")
    type = str
    default = ""

    def store(self):
        super().apply()
        file_util.delete_lines_starting_with(CONFIG_FILE, "welcometext=")
        if self.value:
            file_util.prepend_to_file(CONFIG_FILE, "welcometext=%s\n" % self.value)

    def load(self):
        value = option_util.get_option(CONFIG_FILE, "welcometext=")
        return value


class ServerPasswordOption(service_option_template.TailsServiceOption):
    DEFAULT_LENGTH = 20
    name = "server-password"
    name_in_gui = _("Password")
    description = _("Password required to connect to service")
    type = str
    group = "connection"
    masked = True

    @property
    def default(self):
        import logging
        logging.warning("Setting default password")
        return ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in
                       range(self.DEFAULT_LENGTH))

    def store(self):
        file_util.delete_lines_starting_with(CONFIG_FILE, "serverpassword=")
        # This needs to be prepended instead of appended, because there is an "Ice" section at the
        # end of the config file
        file_util.prepend_to_file(CONFIG_FILE, "serverpassword=%s\n" % self.value)

    def load(self):
        value = option_util.get_option(CONFIG_FILE, "serverpassword=")
        return value


class MumbleServer(service_template.TailsService):
    name = "mumble"
    description = _("A voice chat server")
    client_application = "mumble"
    systemd_service = "mumble-server.service"
    packages = ["mumble-server"]
    default_target_port = 64738
    documentation = "file:///usr/share/doc/tails/website/doc/tails_server/mumble.en.html"
    persistent_paths = [CONFIG_FILE]
    icon_name = "mumble"

    db_path = "/var/lib/mumble-server/mumble-server.sqlite"

    @property
    def fingerprint(self):
        connection = sqlite3.connect(self.db_path)
        c = connection.cursor()
        c.execute("SELECT value FROM config WHERE key = 'certificate'")
        cert_string = c.fetchone()[0]
        cert = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, cert_string)
        return cert.digest("sha1").decode()

    @property
    def connection_info(self):
        if not self.address:
            return None

        s = str()
        s += _("Application: %s\n") % self.client_application_in_gui
        s += _("Address: %s\n") % self.address
        s += _("Port: %s\n") % self.virtual_port
        s += _("Client Cookie: %s\n") % self.client_cookie
        s += _("Password: %s\n") % self.options_dict["server-password"].value
        s += _("Certificate SHA-1 Fingerprint: %s") % self.fingerprint
        return s

    options = [
        service_option_template.VirtualPort,
        ServerPasswordOption,
        service_option_template.PersistenceOption,
        service_option_template.AutoStartOption,
        service_option_template.AllowLanOption,
        WelcomeMessageOption,
    ]

service_class = MumbleServer


def main():
    service = service_class()
    args = service.arg_parser.parse_args()
    service.set_up_logging(args)
    service.dispatch_command(args)

if __name__ == "__main__":
    main()
