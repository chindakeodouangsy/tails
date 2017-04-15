class UnknownOptionError(Exception):
    pass


class ServiceAlreadyEnabledError(Exception):
    pass


class ServiceAlreadyInstalledError(Exception):
    pass


class ServiceNotInstalledError(Exception):
    pass


class TorIsNotRunningError(Exception):
    pass


class InvalidStatusError(Exception):
    pass


class AlreadyMountedError(Exception):
    pass


class ReadOnlyOptionError(Exception):
    pass


class OptionNotInitializedError(Exception):
    def __init__(self, option=None):
        msg = "Option %r accessed before it was initialized" % option if option else None
        super().__init__(msg)
