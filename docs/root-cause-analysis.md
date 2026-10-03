# Root-cause analysis: intermittent mouse hand-off with CleverSwitch 1.5.4

Date of analysis: 2026-10-04 (Europe/Istanbul). Windows 11 Pro 10.0.26300, CleverSwitch 1.5.4
(hidapi 0.15.0, Python 3.14 PyInstaller onefile), MX Keys `0xB35B` and MX Master 3 `0xB023` over
direct Bluetooth, channel 1 = Mac, channel 2 = Windows.

## Symptom

The keyboard always followed its Easy-Switch key; the mouse sometimes stayed on the previous computer.
It happened in both directions, mostly when switching back soon after arriving, and "went away" after
waiting. The Mac operator reported: pressing 2 on the Mac moved both devices to Windows, pressing 1 on
Windows moved only the keyboard back.

## Evidence

Source: the 48 MB `-vv` log of the stock build from 2026-10-03 (kept locally as
`logs/stderr-2026-10-03-v1.5.4-stock-vv.log`; extracted timeline in
`timeline-2026-10-03-stock-1.5.4.txt`). With `-vv` the discovery loop logs the full HID enumeration
twice a second, so the exact second a device became openable on Windows is known.

### Every `reconnected` is quantised to the backoff schedule

`HidGateway._try_connect` waits `_backoff` seconds after each failed attempt and doubles it up to
`_RECONNECT_BACKOFF_MAX = 30`. Measured from the disconnect, the attempts fall at +1, +3, +7, +15,
+31, +61, +91, +121, +151 s. Observed:

| Disconnect | Device enumerable again | `reconnected` logged | Attempt offset |
|---|---|---|---|
| 04:46:18 keyboard | 04:46:30 | 04:46:33 | +15 |
| 04:46:18 mouse | 04:48:29 | 04:48:49 | +151 |
| 04:47:15 keyboard | 04:48:28 | 04:48:46 | +91 |
| 04:49:00 mouse | 04:50:02 | 04:50:31 | +91 |
| 04:49:01 keyboard | 04:49:13 | 04:49:16 | +15 |
| 04:51:40 both | 04:53:01 | 04:53:11 | +91 (mouse), +91 (keyboard, from 04:51:40) |

No `reconnected` ever appears off-schedule. The lag between "openable" and "opened" ranged from 3 s to
29 s, and grows with each missed attempt.

### Presses inside the lag drop the mouse command

```text
04:49:13  ENUM present=['0xb35b']                 keyboard back on Windows
04:49:16  'MX Keys' reconnected
04:49:28  HostChangeEvent target_host=1 → Dropping write to pid=0xB023: device disconnected
04:49:36  HostChangeEvent target_host=0 → Dropping write to pid=0xB023: device disconnected
04:49:50  HostChangeEvent target_host=0 → Dropping write to pid=0xB023: device disconnected
04:50:02  ENUM present=['0xb023', '0xb35b']       mouse back on Windows
04:50:31  'MX Master 3' reconnected
```

In this run the mouse was genuinely absent from Windows between 04:49:01 and 04:50:02: the Mac had not
sent it. The Mac runs the same gateway code (`HidGatewayBLE` → `HidGatewayBT` → `HidGateway`), so when
the user pressed 2 on the Mac at ~04:49:10, nine seconds after the mouse arrived there, the Mac's
gateway was still in its own backoff and dropped the write in the same way. Each side's blind window
feeds the other's.

### How the mouse trails the keyboard

Mac → Windows arrival gaps seen: 1 s (04:48:28/29), 0 s (04:53:01), 6 s (00:12:42/48 on 2026-10-04).
The 6 s case is consistent with the Mac side sending the mouse late for the same reason. This gap sets
the minimum useful window for parking a host change on the destination.

### What is not the cause

- **Bluetooth itself.** Whenever the mouse was enumerable Windows had already finished reconnecting;
  Windows always reopened the device successfully on the first attempt after it appeared.
- **Logi Options+.** Its traffic is visible (`HidppResponseEvent ... sw_id=11`, `HidppErrorEvent
  sw_id=2`) but it neither cleared the analytics flags nor interfered with writes. The keyboard's
  Easy-Switch reporting is re-armed by CleverSwitch on every reconnect (`Enabling analytics for CID
  0x00D1..D3`).
- **Stale device cache.** `--clear-cache` was tried by the previous operator with no effect; the cache
  only skips feature discovery.
- **Two daemons.** The two `cleverswitch.exe` processes are the PyInstaller onefile bootstrapper and
  its child (parent/child relationship, one `_MEI<pid>` temp dir).

## Fix

1. `discovery.py` wakes a disconnected gateway as soon as its pid is enumerable
   (`HidGateway.wake()` → interrupts `_backoff_wait`). Reopen latency becomes ≤ one sweep (0.5 s).
2. `_RECONNECT_BACKOFF_MAX` 30 s → 5 s as a safety net for the absent case.
3. Host-change writes to peers carry `defer_ttl=10 s` and `discard_if=lambda: source.connected`;
   the gateway parks the newest such write while disconnected and sends it 1 s after reconnecting
   unless the TTL expired or the source keyboard is already back on this host.
4. `--log-file` with size rotation; `-vv` enumeration dump only on change.

Regression tests: `tests/cleverswitch/gateway/test_hid_gateway_reconnect.py`,
`tests/cleverswitch/discovery/test_discovery_wake.py`,
`tests/cleverswitch/subscriber/test_host_change_defer.py`, `tests/cleverswitch/cli/test_cli_logfile.py`.

## Side findings worth upstreaming

- `HidGateway.__init__` sets `self._stop = threading.Event()`, shadowing `threading.Thread._stop`.
  On Python ≤ 3.12 `Thread.join()` and `is_alive()` call `self._stop()` once the thread has finished
  and raise `TypeError: 'Event' object is not callable` (three upstream tests fail on 3.12). Python
  3.13+ no longer calls it, so the shipped 3.14 build is unaffected.
- Upstream issue #121 ("works once per machine, then 10–15 s to re-arm") matches this analysis.
