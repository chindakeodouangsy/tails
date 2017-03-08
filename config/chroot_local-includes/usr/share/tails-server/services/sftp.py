import shutil
import sh
import os
import random
import string
import logging
import time

from tails_server import _
from tails_server import file_util
from tails_server import service_template
from tails_server import option_template
from tails_server.options.virtual_port import VirtualPort
from tails_server.options.persistence import PersistenceOption
from tails_server.options.autostart import AutoStartOption
from tails_server.options.allow_localhost import AllowLocalhostOption
from tails_server.options.allow_lan import AllowLanOption

TEMPLATE_CONFIG_FILE = "/etc/ssh/sshd_config"


class ServerPasswordOption(option_template.TailsServiceOption):
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

    options = [
        VirtualPort,
        ServerPasswordOption,
        PersistenceOption,
        AutoStartOption,
        AllowLocalhostOption,
        AllowLanOption,
    ]

    user_name = "sftp"

    def __init__(self):
        super().__init__()
        self.chroot_dir = "/var/lib/sftp"
        self.chroot_files_dir = os.path.join(self.chroot_dir, "files")
        self.files_dir = os.path.join(self.state_dir, "files")
        self.config_file = os.path.join(self.state_dir, "config")
        self.secret_key_file = os.path.join(self.state_dir, "ssh_host_ed25519_key")
        self.public_key_file = self.secret_key_file + ".pub"

        self.persistent_paths = [self.files_dir]

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
        s += _("Password: %s\n") % self.options_dict["server-password"].value
        s += _("SSH Public Key: %s") % self.public_key
        return s

    def configure(self):
        # Create user
        sh.adduser("--system", "--group", "--home", "/", "--no-create-home", "--shell",
                   "/bin/false", "--disabled-login", self.user_name)

        # Set user password
        self.options_dict["server-password"].apply()

        # Create files directory
        logging.debug("Creating directory %r", self.files_dir)
        sh.install("-o", "sftp", "-g", "nogroup", "-m", "700", "-d", self.files_dir)

        # Create chroot directory
        logging.debug("Creating directory %r", self.chroot_dir)
        sh.install("-o", "root", "-g", "sftp", "-m", "750", "-d", self.chroot_dir)
        # sh.install("-o", "sftp", "-g", "nogroup", "-m", "700", "-d",
        #            os.path.join(self.chroot_dir, "files"))

        # Copy sshd_config
        logging.debug("Copying %r to %r", TEMPLATE_CONFIG_FILE, self.config_file)
        shutil.copy(TEMPLATE_CONFIG_FILE, self.config_file)

        # Generate new host key
        logging.debug("Generating new host key %r", self.secret_key_file)
        if os.path.exists(self.secret_key_file):
            raise FileExistsError("Secret key file %r already exists. Aborting" %
                                  self.secret_key_file)
        sh.ssh_keygen(sh.echo("n"), "-N", "", "-t", "ed25519", "-f", self.secret_key_file)

        logging.debug("Adjusting config file %r", self.config_file)
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
        file_util.delete_lines_starting_with(self.config_file, "Subsystem")
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

        # Bind mount files directory into chroot
        logging.debug("Bind-mounting %r to %r", self.files_dir, self.chroot_files_dir)
        if not os.path.exists(self.chroot_files_dir):
            os.mkdir(self.chroot_files_dir)
        sh.mount("--bind", self.files_dir, self.chroot_files_dir)

        super().configure()

    def uninstall(self):
        self.delete_user(self.user_name)
        self.unmount(self.chroot_files_dir)
        self.remove_dir(self.chroot_dir)
        super().uninstall()

    @staticmethod
    def delete_user(user):
        try:
            sh.userdel(user)
        except sh.ErrorReturnCode_6:  # User does not exist
            logging.error("Could not delete user %r", user, exc_info=True)
        except sh.ErrorReturnCode_8:  # User is used by a process
            logging.warning("User %r is still used by processes. "
                            "Killing all processes running as %r.", user, user)
            sh.killall("-v", "-u", user)
            time.sleep(5)
            sh.killall("-9", "-v", "-u", user)
            time.sleep(0.1)
            sh.userdel(user)

    @staticmethod
    def unmount(dir_):
        try:
            sh.umount(dir_)
        except sh.ErrorReturnCode_32 as e:  # Error: not mounted
            logging.error(e)

    @staticmethod
    def remove_dir(dir_):
        try:
            sh.rm("-r", dir_)
        except sh.ErrorReturnCode_1 as e:  # Error: No such file or directory
            logging.error(e)


service_class = SFTPServer
