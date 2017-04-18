import tempfile
import os
import sh
import threading
import re
import logging
import yaml
import fcntl

from tails_server.config import INSTALLED_FILE_PATH, APT_LOCK_FILE


class PolicyNoAutostartOnInstallation(object):
    policy_path = "/usr/sbin/policy-rc.d"
    policy_content = """#!/bin/sh\nexit 101"""

    def __enter__(self):
        logging.debug("Setting policy-rc to prevent autostart of services")
        self.tmp_dir = tempfile.mkdtemp()
        self.original_policy_path = None
        if os.path.exists(self.policy_path):
            sh.mv(self.policy_path, self.tmp_dir)
            self.original_policy_path = self.tmp_dir + self.policy_path
        with open(self.policy_path, "w+") as f:
            f.write(self.policy_content)
        os.chmod(self.policy_path, 700)

    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.debug("Restoring policy-rc")
        os.remove(self.policy_path)
        if self.original_policy_path:
            sh.mv(self.original_policy_path, self.policy_path)
        os.rmdir(self.tmp_dir)


class PrepareAptInstallation(object):
    apt_lock_fd = None
    policy_no_autostart_on_installation = PolicyNoAutostartOnInstallation()

    def __enter__(self):
        self.acquire_apt_lock()
        self.policy_no_autostart_on_installation.__enter__()

    def acquire_apt_lock(self):
        self.ensure_dir_exists()
        self.apt_lock_fd = open(APT_LOCK_FILE, "w+")
        fcntl.flock(self.apt_lock_fd, fcntl.LOCK_EX)
        self.apt_lock_fd.write(str(os.getpid()))

    def ensure_dir_exists(self):
        apt_lock_file_dir = os.path.dirname(APT_LOCK_FILE)
        if not os.path.exists(apt_lock_file_dir):
            sh.install("-m", 700, "-d", apt_lock_file_dir)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.policy_no_autostart_on_installation.__exit__(exc_type, exc_val, exc_tb)
        self.release_apt_lock()

    def release_apt_lock(self):
        fcntl.flock(self.apt_lock_fd, fcntl.LOCK_UN)
        self.apt_lock_fd.close()


def run_threaded(function, *args):
    thread = threading.Thread(target=function, args=args)
    thread.start()


def is_valid_onion_address(address):
    return re.match("^[a-z2-7]{16}\.onion$", address)


def is_valid_port(port):
    return re.match("^[0-9]{0,5}$", port)


def get_installed_services():
    try:
        with open(INSTALLED_FILE_PATH) as f:
            return set(yaml.load(f.read()))
    except (FileNotFoundError, TypeError):
        # create empty "installed" file
        with open(INSTALLED_FILE_PATH, "w+") as f:
            f.write(yaml.dump(list(), default_flow_style=False))
        return set()


def is_mounted(path):
    try:
        sh.findmnt("--mountpoint", path)
    except sh.ErrorReturnCode_1:
        return False
    return True
