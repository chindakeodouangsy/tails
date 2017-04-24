import tempfile
import os
import sh
import threading
import re
import logging
import yaml
import fcntl

from tails_server.config import INSTALLED_FILE_PATH, APT_LOCK_FILE


class open_locked(object):
    def __init__(self, path, *args, **kwargs):
        self.path = path
        self.args = args
        self.kwargs = kwargs

    def __enter__(self):
        logging.debug("Acquiring file lock on %r", self.path)
        self.fd = open(self.path, *self.args, **self.kwargs).__enter__()
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        return self.fd

    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.debug("Releasing file lock on %r", self.path)
        fcntl.flock(self.fd, fcntl.LOCK_UN)
        self.fd.__exit__(exc_type, exc_val, exc_tb)


class prevent_autostart_on_installation(object):
    policy_path = "/usr/sbin/policy-rc.d"
    policy_content = """#!/bin/sh\nexit 101"""

    def __enter__(self):
        logging.debug("Setting policy-rc to prevent autostart of services")
        self.tmp_dir = tempfile.mkdtemp()
        self.original_policy_path = None
        if os.path.exists(self.policy_path):
            sh.mv(self.policy_path, self.tmp_dir)
            self.original_policy_path = os.path.join(self.tmp_dir, os.path.basename(self.policy_path))
        with open_locked(self.policy_path, "w+") as f:
            f.write(self.policy_content)
        os.chmod(self.policy_path, 700)

    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.debug("Restoring policy-rc")
        os.remove(self.policy_path)
        if self.original_policy_path:
            sh.mv(self.original_policy_path, self.policy_path)
        os.rmdir(self.tmp_dir)


class prepare_apt_installation(object):
    apt_lock_fd = None
    prevent_autostart_cm = prevent_autostart_on_installation()
    open_locked_cm = open_locked(APT_LOCK_FILE, "w+")

    def __enter__(self):
        self.ensure_dir_exists(APT_LOCK_FILE)
        f = self.open_locked_cm.__enter__()
        f.write(str(os.getpid()))
        self.prevent_autostart_cm.__enter__()

    def ensure_dir_exists(self, path):
        dir_ = os.path.dirname(path)
        if not os.path.exists(dir_):
            sh.install("-m", 700, "-d", dir_)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.prevent_autostart_cm.__exit__(exc_type, exc_val, exc_tb)
        self.open_locked_cm.__exit__(exc_type, exc_val, exc_tb)


def run_threaded(function, *args):
    thread = threading.Thread(target=function, args=args)
    thread.start()


def is_valid_onion_address(address):
    return re.match("^[a-z2-7]{16}\.onion$", address)


def is_valid_port(port):
    return re.match("^[0-9]{0,5}$", port)


def get_installed_services():
    try:
        with open_locked(INSTALLED_FILE_PATH) as f:
            return set(yaml.load(f.read()))
    except (FileNotFoundError, TypeError):
        # create empty "installed" file
        with open_locked(INSTALLED_FILE_PATH, "w+") as f:
            f.write(yaml.dump(list(), default_flow_style=False))
        return set()


def is_mounted(path):
    try:
        sh.findmnt("--mountpoint", path)
    except sh.ErrorReturnCode_1:
        return False
    return True
