import subprocess
import logging
import re
import os

from tails_server import _
from tails_server.client_launcher_template import \
    ClientLauncher, ClientLauncherDetail, InvalidArgumentError
from tails_server.config import HELPER_SCRIPTS_DIR, TAILS_USER

ADD_FINGERPRINT_SCRIPT = os.path.join(HELPER_SCRIPTS_DIR, "add-mumble-fingerprint")


class MumbleLauncher(ClientLauncher):
    name = "mumble"
    icon_name = "mumble"

    @property
    def details(self):
        return super().details + [
            ClientLauncherDetail("password", _("Password"), str, required=False),
            ClientLauncherDetail("fingerprint", _("Certificate SHA-1 Fingerprint"), str,
                                 required=False)
        ]

    def check_if_details_sane(self):
        super().check_if_details_sane()
        # Can't sanity check the password, since we don't want to restrict it
        if "fingerprint" in self.values and not \
                self.is_valid_sha1_fingerprint(self.values["fingerprint"]):
            raise InvalidArgumentError("Certificate SHA-1 Fingerprint", self.values["fingerprint"])
        if "password" in self.values and not self.is_valid_password(self.values["password"]):
            raise InvalidArgumentError("Password must not contain colon", self.values["password"])

    @staticmethod
    def is_valid_sha1_fingerprint(fingerprint):
        return re.match("^" + "[A-Za-z0-9]{2}:" * 19 + "[A-Za-z0-9]{2}$", fingerprint)

    @staticmethod
    def is_valid_password(password):
        if not str.isprintable(password):
            return False
        # A colon breaks the URL parsing in the Mumble client (mumble://user:password@...)
        if ":" in password:
            return False
        return True

    def prepare(self):
        super().prepare()
        if "fingerprint" in self.values:
            self.store_certificate_fingerprint()
        if "password" not in self.values:
            self.values["password"] = ""

    def store_certificate_fingerprint(self):
        logging.info("Storing certificate fingerprint")
        fingerprint = self.values["fingerprint"].replace(":", "").lower()
        # XXX: fingerprint, address and port are user controlled, but because subprocess
        # handles escaping and quoting of arguments, this should still be secure.
        subprocess.check_call(["sudo", "-u", TAILS_USER, ADD_FINGERPRINT_SCRIPT,
                               self.values["address"], self.values["port"], fingerprint])

    def launch(self):
        super().launch()
        # XXX: The connection string is user controlled, but because subprocess
        # handles escaping and quoting of arguments, this should still be secure.
        user = "client"
        url = "mumble://%s:%s@%s:%s" % (user, self.values["password"], self.values["address"],
                                        self.values["port"])
        subprocess.Popen(["sudo", "-u", TAILS_USER, "mumble", url])


client_launcher_class = MumbleLauncher
