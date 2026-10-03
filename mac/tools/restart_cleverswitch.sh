#!/bin/bash
# Restart the CleverSwitch LaunchAgent exactly as it runs at login and show its state.
set -euo pipefail
LABEL="com.user.cleverswitch"
launchctl kickstart -k "gui/$(id -u)/$LABEL"
sleep 3
launchctl print "gui/$(id -u)/$LABEL" | grep -E "state = |pid = |program = |arguments|cleverswitch" | sed 's/^[[:space:]]*/  /'
echo "--- log"
tail -n 5 /tmp/cleverswitch.err.log
