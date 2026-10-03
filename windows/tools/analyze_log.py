"""Timeline extractor for CleverSwitch logs.

Prints enumeration presence transitions (which devices Windows could open, from -vv output) plus the
lines that matter for a switch: Easy-Switch events, writes, drops, deferrals, (re)connects.

Usage:
    python analyze_log.py <logfile> [HH:MM:SS]      # optional: only lines at/after this time
"""

import re
import sys

path = sys.argv[1]
only_after = sys.argv[2] if len(sys.argv) > 2 else None
present = None
ts_re = re.compile(r"^(?:(\d{4}-\d\d-\d\d) )?(\d\d:\d\d:\d\d)\s+(\w+)\s+(\S+): (.*)$")
keep = re.compile(
    r"HostChangeEvent|Sending host change|Dropping write|Deferring|deferred|Deferred|Writing to pid|reconnected"
    r"|disconnected|Device disconnected|Failed to connect|Opened bluetooth|fully discovered|starting|interrupted"
    r"|Discarding|is back|Enabling analytics|Received HID event from pid=0xB023: 11ff0a1f|Write failed"
)
try:
    for line in open(path, encoding="utf-8", errors="replace"):
        m = ts_re.match(line.rstrip("\n"))
        if not m:
            continue
        date, ts, lvl, logger, msg = m.groups()
        if only_after and ts < only_after:
            continue
        stamp = f"{date} {ts}" if date else ts
        if msg.startswith("All suitable hid devices="):
            pids = set(int(x) for x in re.findall(r"(\d+): \[HidDeviceInfo", msg))
            if present is None or pids != present:
                print(f"{stamp}  ENUM  present={sorted(hex(p) for p in pids)}")
                present = pids
            continue
        if keep.search(msg):
            print(f"{stamp}  {msg[:150]}")
except (BrokenPipeError, OSError):
    pass
