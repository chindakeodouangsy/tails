from tails_server import _
from tails_server.option_template import TailsServiceOption


class VirtualPort(TailsServiceOption):
    name = "virtual-port"
    name_in_gui = _("Port")
    description = _("Port opened on the Tor network")
    type = int
    group = "connection"

    @property
    def default(self):
        return self.service.default_virtual_port
