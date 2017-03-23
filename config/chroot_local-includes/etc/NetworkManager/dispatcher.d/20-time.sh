#!/bin/sh

set -e

# Import wait_until()
. /usr/local/lib/tails-shell-library/common.sh

# Import tor_is_working()
. /usr/local/lib/tails-shell-library/tor.sh

### Exit conditions

# Run only when the interface is not "lo":
if [ "$1" = "lo" ]; then
	exit 0
fi

# Run whenever an interface gets "up", not otherwise:
if [ "$2" != "up" ]; then
	exit 0
fi

### Main

# Magic mechanism that syncs the time :)
touch /waiting_for_time_sync
while [ ! -e /time_is_synced ]; do
    sleep 1
done

wait_until 120 tor_is_working
systemctl restart htpdate.service
