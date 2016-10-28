import tempfile
import os
import shutil
import threading
import re
import logging
import yaml

from tails_server.config import INSTALLED_FILE_PATH


class PolicyNoAutostartOnInstallation(object):
    policy_path = "/usr/sbin/policy-rc.d"
    policy_content = """#!/bin/sh\nexit 101"""

    def __enter__(self):
        logging.debug("Setting policy-rc to prevent autostart of services")
        self.tmp_dir = tempfile.mkdtemp()
        self.old_policy_path = None
        if os.path.exists(self.policy_path):
            shutil.move(self.policy_path, self.tmp_dir)
            self.old_policy_path = os.path.join(self.tmp_dir, self.policy_path)
        with open(self.policy_path, "w+") as f:
            f.write(self.policy_content)
        os.chmod(self.policy_path, 700)

    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.debug("Resetting policy-rc")
        os.remove(self.policy_path)
        if self.old_policy_path:
            shutil.move(self.old_policy_path, self.policy_path)
        os.rmdir(self.tmp_dir)


def run_threaded(function, *args):
    thread = threading.Thread(target=function, args=args)
    thread.start()


def is_valid_onion_address(address):
    return re.match("^[a-z2-7]{16}\.onion$", address)


def is_valid_port(port):
    return re.match("^[0-9]{0,5}$", port)


def is_valid_client_cookie(cookie):
    return re.match("^[A-Za-z0-9+/.]{22}$", cookie)


def get_installed_services():
    try:
        with open(INSTALLED_FILE_PATH) as f:
            return set(yaml.load(f.read()))
    except (FileNotFoundError, TypeError):
        # create empty "installed" file
        with open(INSTALLED_FILE_PATH, "w+") as f:
            f.write(yaml.dump(list(), default_flow_style=False))
        return set()