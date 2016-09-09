import subprocess
import os

from tails_server import _
from tails_server.client_launcher_template import ClientLauncher, ClientLauncherDetail
from tails_server.config import HELPER_SCRIPTS_DIR

CREATE_CONFIG_SCRIPT = os.path.join(HELPER_SCRIPTS_DIR, "create-gobby-config")


class GobbyLauncher(ClientLauncher):
    name = "gobby"
    icon_name = "gobby-0.5"

    @property
    def details(self):
        return super().details + [
            ClientLauncherDetail("password", _("Password"), str, required=False),
        ]

    def prepare(self):
        super().prepare()
        if "password" not in self.values:
            self.values["password"] = ""
        self.create_config_file()

    @staticmethod
    def create_config_file():
        subprocess.check_call(["sudo", "-u", "amnesia", CREATE_CONFIG_SCRIPT])

    def launch(self):
        super().launch()
        # XXX: The connection string is user controlled, but because subprocess
        # handles escaping and quoting of arguments, this should still be secure.
        subprocess.Popen(["sudo", "-u", "amnesia", "gobby", "-c", "%s:%s" %
                          (self.values["address"], self.values["port"])])


client_launcher_class = GobbyLauncher
