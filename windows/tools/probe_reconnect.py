"""Reconnect probe: asks the MX Master 3 to 'switch' to the host it is already on.

Some Logitech firmware treats setCurrentHost(current) as a link reset, which drops and re-establishes
the Bluetooth link without involving the other computer. If it does, the CleverSwitch log must show the
patched path: 'Device disconnected' -> 'Reconnect wait interrupted' / reopen -> 'reconnected' within
about a second of the device reappearing. If the firmware ignores the request nothing happens. No
channel assignment is changed either way.

Run with a Python that can import the patched tree (3.10+). hidapi.dll is picked up from
<repo>/cleverswitch/hidapi.dll.

    python probe_reconnect.py [--host-index 1] [--pid 0xB023] [--change-host-idx 0x0A]
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TREE = REPO / "cleverswitch"
sys.path.insert(0, str(TREE / "src"))
if sys.platform == "win32":
    os.add_dll_directory(str(TREE))  # hidapi.dll

from cleverswitch.hidpp.protocol import build_msg  # noqa: E402
from cleverswitch.hidpp.transport import HIDTransport, enumerate_hid_devices  # noqa: E402

SW_ID = 0x0F


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pid", type=lambda s: int(s, 0), default=0xB023, help="Bluetooth HID PID (default MX Master 3)")
    p.add_argument("--change-host-idx", type=lambda s: int(s, 0), default=0x0A, help="feature 0x1814 index on the device")
    p.add_argument("--host-index", type=int, default=1, help="0-based host to 'switch' to; use the current one")
    p.add_argument("--watch", type=int, default=30, help="seconds to report enumeration state afterwards")
    args = p.parse_args()

    devices = enumerate_hid_devices(product_id=args.pid)
    if args.pid not in devices:
        print(f"pid=0x{args.pid:04X} is not connected to this computer right now; nothing to probe.")
        return 2

    collection = next((d for d in devices[args.pid] if d.usage == 0x0202), devices[args.pid][0])
    msg = build_msg(0xFF, (args.change_host_idx << 8) | 0x10 | SW_ID, bytes([args.host_index]))
    print(f"writing {msg.hex()} to {collection.path!r}")
    transport = HIDTransport(collection.connection_type, collection.path)
    try:
        transport.write_output_report(msg)
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            reply = transport.read(200)
            if reply:
                print(f"reply {reply.hex()}")
    finally:
        transport.close()

    for _ in range(args.watch):
        time.sleep(1.0)
        present = args.pid in enumerate_hid_devices(product_id=args.pid)
        print(f"{time.strftime('%H:%M:%S')} pid=0x{args.pid:04X} enumerable: {present}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
