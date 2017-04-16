import sh
import stem
import stem.control
import logging

from tails_server.config import TOR_BOOTSTRAPPED_TARGET


def tor_has_bootstrapped():
    try:
        sh.systemctl("is-active", TOR_BOOTSTRAPPED_TARGET)
    except sh.ErrorReturnCode_3:  # inactive
        return False
    return True


def is_published(address):
    # XXX: This only works with create_ephemeral_hidden_service, which we will only be able to
    # use with tor >= 2.9.X
    service_id = address.replace(".onion", "")
    c = stem.control.Controller.from_socket_file()
    c.authenticate()
    try:
        published_service_ids = c.get_info("onions/detached").split("\n")
        return service_id in published_service_ids
    except stem.ProtocolError as e:
        if e.args != stem.ProtocolError("GETINFO response didn't have an OK status:\nNo onion "
                                        "services of the specified type.").args:
            logging.error("Got a ProtocolError from stem", exc_info=True)
