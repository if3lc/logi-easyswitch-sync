#!/bin/bash
# Follow the CleverSwitch log. With -v the daemon logs every mouse/keyboard HID report; those and the
# bleak delegate chatter are filtered out so switches, (re)connects and writes stay readable.
# Usage: mac/tools/tail_log.sh [lines]
exec tail -n "${1:-40}" -f /tmp/cleverswitch.err.log \
    | grep --line-buffered -v -E "Received HID event|PeripheralDelegate|Write Characteristic|Services resolved|Using selector|^  System Settings"
