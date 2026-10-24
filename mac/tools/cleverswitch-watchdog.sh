#!/bin/bash
# CleverSwitch watchdog (macOS). Runs every 10 minutes from the LaunchAgent
# com.user.cleverswitch-watchdog. Two jobs:
#  1. Keep /tmp/cleverswitch.err.log under 30 MB (the daemon may run with -v).
#  2. While BOTH Logitech devices are away (on the other computer), restart the
#     CleverSwitch LaunchAgent if the running instance is older than 20 minutes,
#     so every return to the Mac starts from a fresh HID/BLE session. Seen on
#     2026-10-23/24: an instance running for days kept tracking connects but
#     stopped seeing Easy-Switch presses; a restart fixed it. Restarting while the
#     devices are away loses nothing - there is nothing to relay.
set -u
LABEL="com.user.cleverswitch"
LOG="/tmp/cleverswitch.err.log"
WLOG="/tmp/cleverswitch-watchdog.log"
MAX_LOG_BYTES=$((30 * 1024 * 1024))
MIN_AGE_SECONDS=1200

note() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$WLOG"; }

# 1. log rotation (one generation)
if [ -f "$LOG" ] && [ "$(stat -f%z "$LOG")" -gt "$MAX_LOG_BYTES" ]; then
    cp "$LOG" "$LOG.1" && : > "$LOG" && note "rotated $LOG"
fi

# 2. restart while the devices are away
if system_profiler SPBluetoothDataType 2>/dev/null | awk '
    /^ +Connected:/      { c = 1 }
    /^ +Not Connected:/  { c = 0 }
    c && /^ +(MX Keys|MX Master 3):/ { found = 1 }
    END { exit !found }'; then
    exit 0   # at least one device is connected to this Mac: leave the daemon alone
fi

pid="$(launchctl print "gui/$(id -u)/$LABEL" 2>/dev/null | awk '/^\tpid = /{print $3}')"
[ -n "$pid" ] || exit 0
etime="$(ps -o etime= -p "$pid" 2>/dev/null | tr -d ' ')"
[ -n "$etime" ] || exit 0
# etime formats: mm:ss, hh:mm:ss, dd-hh:mm:ss
days=0; rest="$etime"
case "$rest" in *-*) days="${rest%%-*}"; rest="${rest#*-}";; esac
IFS=: read -r a b c <<< "$rest"
if [ -z "${c:-}" ]; then secs=$((10#$a * 60 + 10#$b)); else secs=$((10#$a * 3600 + 10#$b * 60 + 10#$c)); fi
secs=$((secs + days * 86400))
if [ "$secs" -ge "$MIN_AGE_SECONDS" ]; then
    launchctl kickstart -k "gui/$(id -u)/$LABEL" && note "restarted $LABEL (pid $pid was up ${etime}, devices away)"
fi
