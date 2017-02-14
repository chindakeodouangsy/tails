import subprocess

from tails_server.client_launcher_template import ClientLauncher


class TorBrowserLauncher(ClientLauncher):
    name = "tor-browser"
    icon_name = "tor-browser"

    def prepare(self):
        super().prepare()

    def launch(self):
        super().launch()
        # XXX: The connection string is user controlled, but because subprocess
        # handles escaping and quoting of arguments, this should still be secure.
        subprocess.Popen(["sudo", "-u", "amnesia", "tor-browser",
                          "%s:%s" %(self.values["address"], self.values["port"])])


client_launcher_class = TorBrowserLauncher
