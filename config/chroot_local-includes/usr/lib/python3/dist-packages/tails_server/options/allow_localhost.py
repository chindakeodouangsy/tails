import sh

from tails_server import _
from tails_server.option_template import TailsServiceOption


class AllowLocalhostOption(TailsServiceOption):
    name = "allow-localhost"
    name_in_gui = _("Allow localhost")
    description = _("Allow connections from localhost")
    type = bool
    default = False
    group = "generic-checkbox"

    @property
    def rule(self):
        return ("OUTPUT", "--out-interface", "lo", "--protocol", "tcp", "--dport",
                self.service.target_port, "--jump", "ACCEPT")

    def store(self):
        super().store()
        if self.value:
            self.accept_localhost_connections()
        else:
            self.reject_localhost_connections()

    def accept_localhost_connections(self):
        sh.iptables("-I", *self.rule)

    def reject_localhost_connections(self):
        sh.iptables("-D", *self.rule)

    def load(self):
        return self.is_allowed()

    def is_allowed(self):
        try:
            sh.iptables("-C", *self.rule)
            return True
        except sh.ErrorReturnCode_1:
            return False

    def clean_up(self):
        super().clean_up()
        if self.value:
            self.reject_localhost_connections()
