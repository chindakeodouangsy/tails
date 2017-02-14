import tempfile
import os
import sh
import threading
import re
import logging
import yaml
from threading import Lock

from tails_server.config import INSTALLED_FILE_PATH


class PolicyNoAutostartOnInstallation(object):
    policy_path = "/usr/sbin/policy-rc.d"
    policy_content = """#!/bin/sh\nexit 101"""

    def __enter__(self):
        logging.debug("Setting policy-rc to prevent autostart of services")
        self.tmp_dir = tempfile.mkdtemp()
        self.original_policy_path = None
        if os.path.exists(self.policy_path):
            sh.mv(self.policy_path, self.tmp_dir)
            self.original_policy_path = os.path.join(self.tmp_dir, self.policy_path)
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
    policy_no_autostart_on_installation = PolicyNoAutostartOnInstallation()
    lock = Lock()

    def __enter__(self):
        self.lock.acquire()
        self.policy_no_autostart_on_installation.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.policy_no_autostart_on_installation.__exit__(exc_type, exc_val, exc_tb)
        self.lock.release()


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