#!/usr/bin/env python3

import string
import random
import sqlite3
import OpenSSL.crypto

from tails_server import file_util
from tails_server import option_util
from tails_server import service_template
from tails_server import service_option_template

CONFIG_FILE = "/etc/mumble-server.ini"


class WelcomeMessageOption(service_option_template.TailsServiceOption):
    name = "welcome-message"
    description = "Welcome message sent to clients when they connect"
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
    name_in_gui = "Password"
    description = "Password required to connect to service"
    type = str
    group = "connection"

    @property
    def default(self):
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
    systemd_service = "mumble-server.service"
    description = "A voice chat server"
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
    def connection_string(self):
        if not self.address:
            return None

        mime_string = "mumble://username:%s@%s" % (self.options_dict["server-password"].value,
                                                   self.address)
        if self.virtual_port != self.default_target_port:
            mime_string += ":%s" % self.virtual_port

        s = "%s\n" % mime_string
        s += "Address: %s\n" % self.address
        s += "Port: %s\n" % self.virtual_port
        s += "Password: %s\n" % self.options_dict["server-password"].value
        s += "Certificate SHA1 Fingerprint: %s" % self.fingerprint
        return s

    @property
    def connection_string_in_gui(self):
        if not self.address:
            return None

        # masked_password = "*" * len(self.options_dict["server-password"].value)
        return self.connection_string.replace("\n", "; ")

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
