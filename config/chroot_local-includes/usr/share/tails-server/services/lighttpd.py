#!/usr/bin/env python3

from tails_server import _
from tails_server import service_template
from tails_server.options.virtual_port import VirtualPort
from tails_server.options.persistence import PersistenceOption
from tails_server.options.autostart import AutoStartOption
from tails_server.options.allow_localhost import AllowLocalhostOption
from tails_server.options.allow_lan import AllowLanOption

CONFIG_DIR = "/etc/lighttpd"


class LighttpdServer(service_template.TailsService):
    name = "lighttpd"
    name_in_gui = "lighttpd"
    description = _("A lightweight web server")
    client_application = "tor-browser"
    packages = ["lighttpd"]
    default_target_port = 80
    documentation = "file:///usr/share/doc/tails/website/doc/tails_server/lighttpd.en.html"
    persistent_paths = [CONFIG_DIR]

    options = [
        VirtualPort,
        PersistenceOption,
        AutoStartOption,
        AllowLocalhostOption,
        AllowLanOption,
    ]

service_class = LighttpdServer


def main():
    service = service_class()
    args = service.arg_parser.parse_args()
    service.set_up_logging(args)
    service.dispatch_command(args)

if __name__ == "__main__":
    main()
