from tails_server import _
from tails_server import service_template
from tails_server.options.virtual_port import VirtualPort
from tails_server.options.persistence import PersistenceOption
from tails_server.options.autostart import AutoStartOption
from tails_server.util import open_locked
from tails_server import option_template

import re
import os

# Users that add additional VirtualHost entries must list them after
# the default one which will be used for the hidden service.
DEFAULT_CONFIG = """
modules_enabled = {
  "roster";   -- Allow users to have a roster.
  "saslauth"; -- Authentication for clients. Required for clients to log in.
  "disco";    -- Service discovery (notifies clients about muc server, etc.).
  "private";  -- Private XML storage (for room bookmarks, etc.).
  "register"; -- Allow users to register on this server using a client and change passwords.
  "posix";    -- POSIX functionality, sends server to background, enables syslog, etc.
};
modules_disabled = {
  --"offline"; -- Store offline messages
  "s2s"; -- Handle server-to-server connections
};
allow_registration = true;
interfaces = { "localhost" }
daemonize = true;
log = { info = "*syslog"; }
pidfile = "/var/run/prosody/prosody.pid";
-- The following two entries are controlled by Tails Server -- do not edit!
Component "conference.localhost" "muc"
VirtualHost "localhost"
"""

CONFIG_DIR = '/etc/prosody'
CONFIG_FILE = os.path.join(CONFIG_DIR, 'prosody.cfg.lua')
DATA_DIR = '/var/lib/prosody'

class OfflineMessaging(option_template.TailsServiceOption):
    name = "offline-messaging"
    name_in_gui = "Offline messaging"
    description = "When enabled, messages sent to an offline user are " + \
                  "delivered the next time they log in"
    default = True
    type = bool
    group = "advanced"

    def store(self):
        self.service.update_config(
            '^\s*(--)?\s*"offline";',
            '  {}"offline";'.format('--' if self.value else '')
        )

    def load(self):
        return bool(re.match('^\s*"offline";', self.service.get_config()))

class ProsodyServer(service_template.TailsService):
    name = 'prosody'
    description = _('Jabber/XMPP server')
    client_application = 'pidgin'
    systemd_service = 'prosody.service'
    packages = ['prosody']
    default_target_port = 5222
    documentation = 'file:///usr/share/doc/tails/website/doc/tails_server/prosody.en.html'
    persistent_paths = [CONFIG_DIR, DATA_DIR]
    icon_name = 'prosody'

    options = [
        VirtualPort,
        PersistenceOption,
        AutoStartOption,
        OfflineMessaging,
    ]

    def configure(self):
        super().configure()
        with open_locked(CONFIG_FILE, 'w') as f:
            f.write(DEFAULT_CONFIG)

    def get_config(self):
        if not os.path.exists(CONFIG_FILE):
            raise FileNotFoundError(
                'File %r is required but could not be found'.format(CONFIG_FILE)
            )
        with open_locked(CONFIG_FILE, 'r') as f:
            return f.read()

    def update_config(self, *args, count = 1):
        if len(args) == 2 and all(isinstance(x, str) for x in args):
            replacements = [args]
        elif len(args) == 1 and any(isinstance(args[0], t) for t in [tuple, list]):
            replacements = args[0]
        else:
            raise(ValueError('invalid arguments'))
        config = self.get_config()
        with open_locked(CONFIG_FILE, 'w') as f:
            for pattern, replacement in replacements:
                config = re.sub(
                    pattern, replacement, config,
                    flags = re.MULTILINE, count = count
                )
            f.write(config)
        if self.is_running:
            self.stop()
            self.start()

    def set_virtual_host(self, address):
        replacements = (
            ('^Component\s.*\s"muc"$',
             'Component "conference.{}" "muc"'.format(address)),
            ('^VirtualHost\s.*$',
             'VirtualHost "{}"'.format(address)),
        )
        self.update_config(replacements)

    def set_onion_address(self, address: str):
        super().set_onion_address(address)
        self.set_virtual_host(address + ".onion")

    def remove_onion_address(self):
        super().remove_onion_address()
        self.set_virtual_host('localhost')

service_class = ProsodyServer
