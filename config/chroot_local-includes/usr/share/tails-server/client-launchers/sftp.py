import subprocess
import logging
import os
import re

from tails_server import _
from tails_server.client_launcher_template import \
    ClientLauncher, ClientLauncherDetail, InvalidArgumentError
from tails_server.config import HELPER_SCRIPTS_DIR, TAILS_USER

ADD_KNOWN_HOST_SCRIPT = os.path.join(HELPER_SCRIPTS_DIR, "add-ssh-known-host")


class NautilusLauncher(ClientLauncher):
    name = "nautilus"
    name_in_gui = "Files"
    icon_name = "network"
    user_name = "sftp"

    @property
    def details(self):
        return super().details + [
            ClientLauncherDetail("password", _("Password"), str, required=False),
            ClientLauncherDetail("key", _("SSH Public Key"), str, required=False),
        ]

    def check_if_details_sane(self):
        super().check_if_details_sane()
        # Can't sanity check the password, since we don't want to restrict it
        if "key" in self.values and not self.is_valid_key(self.values["key"]):
            raise InvalidArgumentError("SSH Public Key", self.values["key"])

    @staticmethod
    def is_valid_key(key):
        return re.match("^" + "[A-Za-z0-9-]+ [A-Za-z0-9+/=]+$", key)

    def prepare(self):
        super().prepare()
        if "key" in self.values:
            self.add_key_to_known_hosts()
        if "password" not in self.values:
            self.values["password"] = ""

    def add_key_to_known_hosts(self):
        known_hosts_line = "%s %s" % (self.values["address"], self.values["key"])
        subprocess.check_call(["sudo", "-u", TAILS_USER, ADD_KNOWN_HOST_SCRIPT, known_hosts_line])

    def launch(self):
        super().launch()
        # XXX: The connection string is user controlled, but because subprocess
        # handles escaping and quoting of arguments, this should still be secure.
        url = "sftp://%s@%s:%s" % (self.user_name, self.values["address"], self.values["port"])
        command = ["sudo", "-u", TAILS_USER, "nautilus", url]
        logging.info("Executing %r", " ".join(command))
        subprocess.Popen(command)


client_launcher_class = NautilusLauncher
