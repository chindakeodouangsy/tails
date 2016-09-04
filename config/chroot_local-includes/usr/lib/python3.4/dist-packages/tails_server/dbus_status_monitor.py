import dbus
import dbus.mainloop.glib
from gi.repository import GLib
import threading
import logging

# Note: I used this to understand how to use python-dbus:
#       https://zignar.net/2014/09/08/getting-started-with-dbus-python-systemd/

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)


class ReceiverAlreadyAddedError(Exception):
    pass


class SystemdUnit(object):
    def __init__(self, name, receiver_function):
        self.name = name
        self.receiver_function = receiver_function
        self.path = manager.LoadUnit(name)
        self.proxy = bus.get_object('org.freedesktop.systemd1', str(self.path))
        self.properties = dbus.Interface(self.proxy,
                                         dbus_interface='org.freedesktop.DBus.Properties')

units = dict()
loop = GLib.MainLoop()
bus = dbus.SystemBus()
systemd = bus.get_object('org.freedesktop.systemd1', '/org/freedesktop/systemd1')
manager = dbus.Interface(systemd, dbus_interface='org.freedesktop.systemd1.Manager')
listening = False


def add_unit(unit_name, receiver_function):
    unit = SystemdUnit(unit_name, receiver_function)
    units[unit.path] = unit


def remove_unit(unit_name):
    unit_path = manager.LoadUnit(unit_name)
    del units[unit_path]


def start_listening():
    global listening
    if listening:
        raise ReceiverAlreadyAddedError()
    bus.add_signal_receiver(
        handler_function=on_unit_loaded,
        signal_name="UnitNew",
        dbus_interface='org.freedesktop.systemd1.Manager',
        path=None,
        sender_keyword='sender',
        destination_keyword='destination',
        interface_keyword='interface',
        member_keyword='member',
        path_keyword='path',
        message_keyword='message',
    )
    listening = True
    # This is only needed for debugging, usually the GLib.MainLoop will be started by the GUI
    # self.loop.run()


def stop_listening():
    global listening
    bus.remove_signal_receiver(
        handler_or_match=on_unit_loaded,
        signal_name="UnitNew",
        dbus_interface='org.freedesktop.systemd1.Manager',
        path=None
    )
    listening = False


def on_unit_loaded(id, unit_path, member, **kwargs):
    logging.debug("Got event %r for unit %r", member, unit_path)
    if unit_path not in units:
        return
    unit = units[unit_path]
    active_state, sub_state = query_unit_state(unit)
    logging.debug("Got %r event for unit %r. ActiveState: %r, SubState: %r",
                  member, unit.name, active_state, sub_state)

    unit.receiver_function(active_state, sub_state)
    # XXX: We have to listen to "SubState" too, because if the systemd unit has
    # "RemainAfterExit" enabled, then the ActiveState will remain "active" after the service
    # exited and only the SubState is set to "exited". Now actually, this "RemainAfterExit"
    # should simply not be enabled for units which run a daemon - but unfortunately, all
    # systemd units generated from Sys V init files have this set to true.
    # See https://bugs.launchpad.net/ubuntu/+source/apache2/+bug/1488962/comments/5


def query_unit_state(unit):
    # We have to remove the signal receiver here, because querying the properties could
    # trigger another UnitNew event, resulting endless UnitNew events.
    # See https://github.com/systemd/systemd/issues/570
    #
    # XXX: This will still result in endless UnitNew events if there are multiple processes
    # doing this same thing, e.g. multiple instances of Tails Server.
    # See https://github.com/systemd/systemd/issues/4095
    stop_listening()
    active_state = unit.properties.Get('org.freedesktop.systemd1.Unit', 'ActiveState')
    sub_state = unit.properties.Get('org.freedesktop.systemd1.Unit', 'SubState')
    start_listening()
    return active_state, sub_state


def run():
    if listening:
        logging.debug("D-Bus status monitor already running")
        return
    logging.debug("Starting D-Bus status monitor")
    thread = threading.Thread(target=start_listening)
    thread.start()


def stop():
    logging.debug("Stopping D-Bus status monitor")
    stop_listening()
    if loop.is_running:
        loop.quit()
