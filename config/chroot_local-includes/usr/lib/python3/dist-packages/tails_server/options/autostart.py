from tails_server import _
from tails_server.option_template import TailsServiceOption


class AutoStartOption(TailsServiceOption):
    name = "autostart"
    name_in_gui = _("Autostart")
    description = _("Start service automatically after booting Tails")
    type = bool
    default = False
    group = "generic-checkbox"
