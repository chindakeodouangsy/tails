from logging import getLogger
import abc

from gi.repository import Gtk

from veracrypt_mounter import _
from veracrypt_mounter.volume import Volume

logger = getLogger(__name__)


class VolumeList(object, metaclass=abc.ABCMeta):

    placeholder_label = str()

    def __init__(self, window):
        self.window = window
        self.volumes = list()
        self.list_box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.placeholder_row = Gtk.ListBoxRow(activatable=False, selectable=False)
        self.placeholder_row.add(Gtk.Label(self.placeholder_label))
        self.show_placeholder()

    def __getitem__(self, item):
        return self.volumes[item]

    @staticmethod
    def listbox_header_func(row, before, data=None):
        if not before:
            return
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        row.set_header(separator)

    def add(self, volume: Volume):
        if volume in self.volumes:
            self.update(volume)
            return

        volume.update_list_box_row()
        self.list_box.add(volume.list_box_row)
        self.volumes.append(volume)

        if len(self.volumes) == 1:
            self.hide_placeholder()

        self.list_box.show_all()

    def remove(self, volume: Volume):
        # Note that we can't use any properties and functions of the volume here
        # which use udisks, because the volume might be already removed from udisks
        if volume not in self.volumes:
            logger.warning("Can't remove volume %s: Not in list")
            return

        index = self.volumes.index(volume)
        self.list_box.remove(self.list_box.get_children()[index])
        self.volumes.remove(volume)

        if not self.volumes:
            self.show_placeholder()

        self.list_box.show_all()

    def update(self, volume: Volume):
        self.remove(volume)
        self.add(volume)

    def clear(self):
        for child in self.list_box.get_children():
            self.list_box.remove(child)

    def show_placeholder(self):
        self.list_box.add(self.placeholder_row)

    def hide_placeholder(self):
        self.list_box.remove(self.placeholder_row)


class ContainerList(VolumeList):
    """Manages attached file containers"""
    placeholder_label = _(
        "No file containers added"
    )


class DeviceList(VolumeList):
    """Manages physically connected drives and partitions"""
    placeholder_label = _(
        "No VeraCrypt devices detected"
    )