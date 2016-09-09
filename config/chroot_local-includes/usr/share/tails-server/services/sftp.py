#!/usr/bin/env python3

import shutil
import sh
import os
import random
import string

from tails_server import _
from tails_server import file_util
from tails_server import service_template
from tails_server import service_option_template

TEMPLATE_CONFIG_FILE = "/etc/ssh/sshd_config"


class ServerPasswordOption(service_option_template.TailsServiceOption):
    # We don't use a super long password here, because the user has to type it. This should still
    # be far beyond crackable via SSH.
    DEFAULT_LENGTH = 10
    name = "server-password"
    name_in_gui = _("Password")
    description = _("Password required to connect to service")
    type = str
    group = "connection"
    masked = True

    @property
    def default(self):
        import logging
        logging.warning("Setting default password")
        return ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in
                       range(self.DEFAULT_LENGTH))

    def apply(self):
        super().apply()
        sh.chpasswd(sh.echo("%s:%s" % (self.service.user_name, self.value)))


class SFTPServer(service_template.TailsService):
    name = "sftp"
    name_in_gui = "SFTP"
    description = _("A file sharing service")
    client_application = "nautilus"
    client_application_in_gui = "Files"
    systemd_service = "tails-server-sftp.service"
    packages = ["openssh-server"]
    default_target_port = 22000
    documentation = "file:///usr/share/doc/tails/website/doc/tails_server/sftp.en.html"
    icon_name = "network"

    chroot_dir="/var/lib/sftp"
    persistent_paths = [chroot_dir]

    options = [
        service_option_template.VirtualPort,
        ServerPasswordOption,
        service_option_template.PersistenceOption,
        service_option_template.AutoStartOption,
        service_option_template.AllowLanOption,
    ]

    user_name = "sftp"

    def __init__(self):
        super().__init__()
        self.config_file = os.path.join(self.state_dir, "config")
        self.secret_key_file = os.path.join(self.state_dir, "ssh_host_ed25519_key")
        self.public_key_file = self.secret_key_file + ".pub"

    @property
    def public_key(self):
        with open(self.public_key_file) as f:
            s = f.read()
            return " ".join(s.split()[:-1]).strip()

    @property
    def connection_info(self):
        if not self.address:
            return None

        s = str()
        s += _("Application: %s\n") % self.client_application_in_gui
        s += _("Address: %s:%s\n") % (self.address, self.virtual_port)
        s += _("Client Cookie: %s\n") % self.client_cookie
        s += _("Password: %s\n") % self.options_dict["server-password"].value
        s += _("SSH Public Key: %s") % self.public_key
        return s

    def configure(self):
        # Create user
        sh.adduser("--system", "--group", "--home", "/", "--no-create-home", "--shell",
                   "/bin/false", "--disabled-login", self.user_name)

        # Create chroot directory
        sh.install("-o", "root", "-g", "sftp", "-m", "770", "-d", self.chroot_dir)
        # sh.install("-o", "sftp", "-g", "nogroup", "-m", "700", "-d",
        #            os.path.join(self.chroot_dir, "files"))

        # Copy sshd_config
        shutil.copy(TEMPLATE_CONFIG_FILE, self.config_file)

        # Generate new host key
        sh.ssh_keygen("-N", "", "-t", "ed25519", "-f", self.secret_key_file)

        # Only allow sftp user
        file_util.delete_lines_starting_with(self.config_file, "AllowUsers")
        file_util.delete_lines_starting_with(self.config_file, "AllowGroups")
        file_util.append_to_file(self.config_file, "AllowUsers %s\n" % self.user_name)

        # Set host key
        file_util.delete_lines_starting_with(self.config_file, "HostKey")
        file_util.append_to_file(self.config_file, "HostKey %s\n" % self.secret_key_file)

        # Set Port to 22000
        file_util.delete_lines_starting_with(self.config_file, "Port")
        file_util.append_to_file(self.config_file, "Port %s\n" % self.default_target_port)

        # Disable X11 forwarding
        file_util.delete_lines_starting_with(self.config_file, "X11Forwarding")
        file_util.append_to_file(self.config_file, "X11Forwarding no\n")

        # Disable Stream Forwarding
        file_util.delete_lines_starting_with(self.config_file, "AllowTcpForwarding")
        file_util.append_to_file(self.config_file, "AllowTcpForwarding no\n")
        file_util.delete_lines_starting_with(self.config_file, "AllowStreamLocalForwarding")
        file_util.append_to_file(self.config_file, "AllowStreamLocalForwarding no\n")

        # Disable root login
        file_util.delete_lines_starting_with(self.config_file, "PermitRootLogin")
        file_util.append_to_file(self.config_file, "PermitRootLogin no\n")

        # Set sftp Subsystem to internal-sftp (this makes sftp work without using the shell,
        # so we can set the sftp users shell to /bin/false)
        file_util.delete_lines_starting_with(self.config_file, "Subsystem sftp")
        file_util.append_to_file(self.config_file, "Subsystem sftp internal-sftp\n")

        # Disable commands other than sftp-server
        file_util.delete_lines_starting_with(self.config_file, "ForceCommand")
        file_util.append_to_file(self.config_file, "ForceCommand internal-sftp\n")

        # Set chroot directory
        file_util.delete_lines_starting_with(self.config_file, "ChrootDirectory")
        file_util.append_to_file(self.config_file, "ChrootDirectory %s\n" % self.chroot_dir)

        # Allow login via PAM
        file_util.delete_lines_starting_with(self.config_file, "UsePAM")
        file_util.append_to_file(self.config_file, "UsePAM yes\n")

        super().configure()

    def uninstall(self):
        super().uninstall()
        sh.deluser(self.user_name)
        sh.rm("-r", self.chroot_dir)


service_class = SFTPServer


def main():
    service = service_class()
    args = service.arg_parser.parse_args()
    service.set_up_logging(args)
    service.dispatch_command(args)

if __name__ == "__main__":
    main()
