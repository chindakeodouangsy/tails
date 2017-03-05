# Translation stuff

import os
import gettext


if os.path.exists('po/locale'):
    translation = gettext.translation('tails-server', 'po/locale', fallback=True)
else:
    translation = gettext.translation('tails-server', '/usr/share/locale',
                                      fallback=True)
_ = translation.gettext


# ImportServices class to access and import service modules

import collections
import importlib.machinery
from tails_server.config import SERVICES_DIR


class DuplicateServiceError(Exception):
        pass


class ImportServices(object):

    _services = list()
    _service_names = list()
    _service_module_paths = collections.OrderedDict()
    _service_modules_dict = collections.OrderedDict()

    @property
    def services(self):
        if not self._services:
            self._services = self.get_services()
        return self._services

    @property
    def service_names(self):
        if not self._service_names:
            self._service_names = self.get_service_names()
        return self._service_names

    @property
    def service_module_paths(self):
        if not self._service_module_paths:
            self._service_module_paths = self.get_service_module_paths()
        return self._service_module_paths

    @property
    def service_modules_dict(self):
        if not self._service_modules_dict:
            self._service_modules_dict = self.get_service_modules_dict()
        return self._service_modules_dict

    def get_services(self):
        return [module.service_class() for module in self.service_modules_dict.values()]

    def get_service_modules_dict(self):
        """Import the modules in SERVICES_DIR"""
        service_modules = collections.OrderedDict()
        for service_name in self.service_names:
            module_path = self.service_module_paths[service_name]
            source_file_loader = importlib.machinery.SourceFileLoader(service_name, module_path)
            service_modules[service_name] = source_file_loader.load_module()
        return service_modules

    def get_service_names(self):
        """Extract the service's name from the filenames in SERVICES_DIR"""
        return list(self.service_module_paths.keys())

    def get_service_module_paths(self):
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
        return service_module_paths

import_services = ImportServices()
