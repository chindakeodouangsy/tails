import os
import sh
import logging

from tails_server import _
from tails_server.option_template import TailsServiceOption


class PersistenceOption(TailsServiceOption):
    name = "persistence"
    description = _("Store service configuration and data on the persistent volume")
    type = bool
    default = False
    group = "generic-checkbox"

    def apply(self):
        super().apply()
        if self.value:
            self.make_persistent()
        else:
            self.remove_persistence()

    def clean_up(self):
        super().clean_up()
        if self.value:
            self.remove_persistence()

    def make_persistent(self):
        logging.info("Making %r persistent", self.service.name)
        self.service.create_persistence_dir()
        self.service.create_hs_dir()

        try:
            for record in self.service.persistence_records:
                self.move(record.target_path, record.persistence_path)
        except (sh.ErrorReturnCode_1, FileExistsError):
            logging.error("Error while moving persistent files", exc_info=True)

        self.service.mount_persistent_files()

    def remove_persistence(self):
        logging.info("Removing persistence of %r", self.service.name)
        try:
            self.service.unmount_persistent_files()
        except sh.ErrorReturnCode_32:
            logging.error("Error while unmounting persistent files", exc_info=True)

        try:
            for record in self.service.persistence_records:
                self.move(record.persistence_path, record.target_path)
        except (sh.ErrorReturnCode_1, FileExistsError):
            logging.error("Error while moving persistent files", exc_info=True)

    @staticmethod
    def move(src, dest):
        logging.debug("Moving %r to %r", src, dest)
        if os.path.exists(dest):
            raise FileExistsError("Couldn't move %r to %r, destination %r already exists" %
                                  (src, dest, dest))

        sh.mv(src, dest)
