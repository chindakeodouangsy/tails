#!/bin/sh

# We don't start Tor automatically so *this* is the time
# when it is supposed to start.

# Run only when the interface is not "lo":
if [ $1 = "lo" ]; then
    exit 0
fi

if [ $2 = "up" ]; then
    : # go on, that's what this script is for
elif [ "${2}" = "down" ]; then
    systemctl --no-block stop tails-tor-has-bootstrapped.target
    exit 0
else
    exit 0
fi

# Import tor_control_setconf(), TOR_LOG
. /usr/local/lib/tails-shell-library/tor.sh

# Import tails_netconf()
. /usr/local/lib/tails-shell-library/tails-greeter.sh

# Let the rest of the system know that Tor is not working at the moment.
# This matters e.g. if we have already bootstrapped.
systemctl --no-block restart tails-tor-has-bootstrapped.target

# The Tor syscall sandbox is not compatible with managed proxies.
# We could possibly detect whether the user has configured any such
# thing via Tor Launcher later (e.g. in 60-tor-ready.sh),
# but then we would have to restart Tor again to enable the sandbox.
# Let's avoid doing that, and enable the Sandbox only if no special Tor
# configuration is needed. Too bad users who simply need to configure
# a HTTP proxy or allowed firewall ports won't get the sandboxing, but
# much better than nothing.
if [ "$(tails_netconf)" = "direct" ]; then
    tor_set_in_torrc Sandbox 1
fi

# We would like Tor to be started during init time, even before the
# network is up, and then send it a SIGHUP here to make it start
# bootstrapping swiftly, but it doesn't work because of a bug in
# Tor. Details:
# * https://trac.torproject.org/projects/tor/ticket/1247
# * https://tails.boum.org/bugs/tor_vs_networkmanager/
# To work around this we restart Tor.
( systemctl restart tor@default.service ) &
if [ "$(tails_netconf)" = "obstacle" ]; then
    # XXX wait until Tor's ControlPort is available

    # Enable the transports we support. We cannot do this in general,
    # when bridge mode is not enabled, since we then use seccomp
    # sandboxing.
    tor_control_setconf 'ClientTransportPlugin="obfs2,obfs3,obfs4 exec /usr/bin/obfs4proxy managed"'

    /usr/local/sbin/tails-tor-launcher &

    # Wait until the user has done the Tor Launcher configuration.
    until [ "$(tor_control_getconf DisableNetwork)" = 0 ]; do
        sleep 1
    done
fi
