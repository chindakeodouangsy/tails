import sh

from tails_server import _
from tails_server.option_template import TailsServiceOption


class AllowLanOption(TailsServiceOption):
    name = "allow-lan"
    name_in_gui = _("Allow LAN")
    description = _("Allow connections from the local network")
    type = bool
    default = False
    group = "generic-checkbox"

    @property
    def rules(self):
        return [("INPUT", "--source", subnet, "--protocol", "tcp", "--dport",
                self.service.target_port, "--jump", "ACCEPT")
                for subnet in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")]

    def store(self):
        super().store()
        if self.value:
            self.accept_lan_connections()
        else:
            self.reject_lan_connections()

    def accept_lan_connections(self):
        for rule in self.rules:
            sh.iptables("-I", *rule)

    def reject_lan_connections(self):
        for rule in self.rules:
            sh.iptables("-D", *rule)

    def load(self):
        return self.is_allowed()

    def is_allowed(self):
        return all(self.is_active(rule) for rule in self.rules)

    @staticmethod
    def is_active(rule):
        try:
            sh.iptables("-C", *rule)
            return True
        except sh.ErrorReturnCode_1:
            return False

    def clean_up(self):
        super().clean_up()
        if self.value:
            self.reject_lan_connections()
