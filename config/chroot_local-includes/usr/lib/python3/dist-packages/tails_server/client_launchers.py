import os
import collections
import importlib.machinery
import logging

from tails_server.config import CLIENT_LAUNCHERS_DIR


class DuplicateClientError(Exception):
    pass

client_names = list()
module_paths = collections.OrderedDict()


def load_client_names():
    """Extract the client's name from the filenames in CLIENT_LAUNCHERS_DIR"""
    global client_names
    global module_paths
    module_paths = collections.OrderedDict()
    filenames = os.listdir(CLIENT_LAUNCHERS_DIR)
    filenames.sort()
    for filename in filenames:
        root = os.path.splitext(filename)[0]
        name = os.path.basename(root)
        if name.startswith("__"):
            continue
        if name in module_paths:
            raise DuplicateClientError("Multiple files for client %r" % root)
        module_paths[name] = os.path.join(CLIENT_LAUNCHERS_DIR, filename)
    client_names = list(module_paths.keys())


def import_client_launcher_modules():
    """Import the modules in the package"""
    modules = collections.OrderedDict()
    for client_name in client_names:
        logging.debug("Importing client launcher %r", client_name)
        module_path = module_paths[client_name]
        try:
            source_file_loader = importlib.machinery.SourceFileLoader(client_name, module_path)
            modules[client_name] = source_file_loader.load_module()
        except:
            logging.error("Error: Couldn't import module %r", module_path)
            raise
    return modules

load_client_names()
