import os
import collections
import importlib.machinery

from tails_server.config import SERVICES_DIR

service_names = list()
service_module_paths = collections.OrderedDict()


class DuplicateServiceError(Exception):
    pass


def load_service_names():
    """Extract the service's name from the filenames in SERVICES_DIR"""
    global service_names
    global service_module_paths
    service_module_paths = collections.OrderedDict()
    filenames = os.listdir(SERVICES_DIR)
    filenames.sort()
    for filename in filenames:
        root = os.path.splitext(filename)[0]
        name = os.path.basename(root)
        if name.startswith("__"):
            continue
        if name in service_module_paths:
            raise DuplicateServiceError("Multiple files for service %r" % root)
        service_module_paths[name] = os.path.join(SERVICES_DIR, filename)
    service_names = list(service_module_paths.keys())


def import_service_modules():
    """Import the modules in SERVICES_DIR"""
    service_modules = collections.OrderedDict()
    for service_name in service_names:
        module_path = service_module_paths[service_name]
        source_file_loader = importlib.machinery.SourceFileLoader(service_name, module_path)
        service_modules[service_name] = source_file_loader.load_module()
    return service_modules

load_service_names()
