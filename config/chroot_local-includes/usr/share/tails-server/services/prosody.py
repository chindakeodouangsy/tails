from tails_server import _
from tails_server import service_template
from tails_server.options.virtual_port import VirtualPort
from tails_server.options.persistence import PersistenceOption
from tails_server.options.autostart import AutoStartOption
from tails_server.util import open_locked

import re
import os

# Users that add additional VirtualHost entries must list them after
# the default one which will be used for the hidden service.
CONFIG = """
modules_enabled = {
  "roster";   -- Allow users to have a roster.
  "saslauth"; -- Authentication for clients. Required for clients to log in.
  "disco";    -- Service discovery (notifies clients about muc server, etc.).
  "private";  -- Private XML storage (for room bookmarks, etc.).
  "register"; -- Allow users to register on this server using a client and change passwords.
  "posix";    -- POSIX functionality, sends server to background, enables syslog, etc.
};
modules_disabled = {
  "offline"; -- Store offline messages
  "s2s"; -- Handle server-to-server connections
};
allow_registration = true;
interfaces = { "localhost" }
daemonize = true;
log = { info = "*syslog"; }
pidfile = "/var/run/prosody/prosody.pid";
Component "conference.localhost" "muc"
VirtualHost "localhost"
"""

CONFIG_DIR = '/etc/prosody'
CONFIG_FILE = os.path.join(CONFIG_DIR, 'prosody.cfg.lua')
DATA_DIR = '/var/lib/prosody'

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
    ]

    def configure(self):
        super().configure()
        with open_locked(CONFIG_FILE, 'w') as f:
            f.write(CONFIG)

    def set_virtual_host(self, address):
        with open_locked(CONFIG_FILE, 'r') as f:
            config = f.read()
        with open_locked(CONFIG_FILE, 'w') as f:
            # We only replace the first occurrence to allow users
            # adding their own VirtualHost:s (*after* the default one)
            replacements = (
                ('^VirtualHost\s.*$',
                 'VirtualHost "{}"'.format(address)),
            )
            for pattern, replacement in replacements:
                config = re.sub(
                    pattern, replacement, config, flags = re.MULTILINE, count = 1
                )
            f.write(config)
        self.stop()
        self.start()

    def set_onion_address(self, address: str):
        super().set_onion_address(address)
        self.set_virtual_host(address + ".onion")

    def remove_onion_address(self):
        super().remove_onion_address()
        self.set_virtual_host('localhost')

service_class = ProsodyServer
