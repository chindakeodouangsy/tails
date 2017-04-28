import subprocess
import os

from tails_server import _
from tails_server.client_launcher_template import \
    ClientLauncher, ClientLauncherDetail
from tails_server.config import HELPER_SCRIPTS_DIR, TAILS_USER


class PidginLauncher(ClientLauncher):
    name = 'pidgin'
    icon_name = 'pidgin'

    @property
    def details(self):
        return super().details + [
            ClientLauncherDetail('username', _('Username'), str, required=True),
            ClientLauncherDetail('password', _('Password'), str, required=True),
        ]

    def prepare(self):
        super().prepare()

    @staticmethod
    def pidgin_create_account(domain, port, username, password):
        account_registration_script = os.path.join(
            HELPER_SCRIPTS_DIR, 'create-pidgin-xmpp-account'
        )
        p = subprocess.Popen([
            'sudo', '-u', TAILS_USER, 'python3', account_registration_script,
            domain, port, username, password
        ])

    def launch(self):
        super().launch()
        account = self.values['username'] + '@' + self.values['address'] + '/'
        p = subprocess.Popen(
            ['pgrep', '--euid', TAILS_USER, '--full', '^/usr/bin/pidgin'],
            stdout=subprocess.PIPE
        )
        pidgin_is_running = p.wait() == 0
        if not pidgin_is_running:
            subprocess.Popen(['sudo', '-u', TAILS_USER, 'pidgin'])
        self.pidgin_create_account(
            self.values['address'], self.values['port'],
            self.values['username'], self.values['password']
        )


client_launcher_class = PidginLauncher
