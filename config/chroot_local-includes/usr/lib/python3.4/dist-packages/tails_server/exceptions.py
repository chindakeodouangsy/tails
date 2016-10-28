class UnknownOptionError(Exception):
    pass


class ServiceAlreadyEnabledError(Exception):
    pass


class ServiceNotInstalledError(Exception):
    pass


class TorIsNotRunningError(Exception):
    pass


class InvalidStatusError(Exception):
    pass
