# Hand-off between the Windows side and the Mac side

Both operators (people or agents) work from this file. Append, do not rewrite history. Sign entries
`[Windows]` or `[Mac]` with a date and time in Europe/Istanbul. Keep raw log excerpts short and put
them under "Log excerpts"; keep decisions under "Messages".

## Facts both sides rely on

- Channel **1 = Mac**, channel **2 = Windows** on both devices (0-based host index 0 and 1).
- Keyboard MX Keys: Bluetooth PID `0xB35B`; mouse MX Master 3: PID `0xB023`; both slot `0xFF`.
- Feature indexes on these units: keyboard `0x1814` → 9, `0x1B04` → 8; mouse `0x1814` → `0x0A`.
- Host-change writes: keyboard `11ff091f0X000000…`, mouse `11ff0a1f0X000000…` (`X` = host index).
  The mouse echoes `11ff0a1f00…` after a successful write.
- The keyboard reports Easy-Switch presses via analytics (`setCidReporting` byte 9 = `0x03`) for
  CIDs `0x00D1`, `0x00D2`, `0x00D3`; native switching is untouched.
- Mac: Karabiner-Elements Ctrl+H/J/K/L mappings must stay; CleverSwitch 1.5.4 was installed with
  `brew tap mikalaibarysevich/cleverswitch && brew install cleverswitch && brew services start cleverswitch`
  and Input Monitoring permission granted.
- Windows: Logi Options+ agent runs alongside; leave it.

## Status

| Side | Build | Autostart | Verified |
|---|---|---|---|
| Windows | `1.5.4+reconnect.2` (this repo, `windows/dist`) | Startup folder VBS, `-vv --log-file` | unit tests, build, start, rollback round trip; live switching not yet observed (devices were on the Mac) |
| Mac | stock 1.5.4 (Homebrew) | `brew services` | works once per side, then slow to re-arm (same bug) |

## Open tasks

### Mac
1. Apply `patches/cleverswitch-1.5.4-reconnect-src-only.patch` to the installed package
   (steps in `mac/APPLY.md`), restart the service, confirm the daemon starts.
2. Enable verbose logging for the service if it is not already (`-v` is enough; `-vv` is cheap with
   the patch) so `Reconnect wait interrupted`, `Deferring write`, `Sending deferred write` are visible.
3. Run the verification protocol (README) from the Mac side and append the Mac log excerpt for each
   cycle below, with timestamps.
4. Report anything unexpected in `brew services` (plist args, log path) under Messages.

### Windows
1. Keep `logs\cleverswitch.log` and run `windows/tools/analyze_log.py` after the Mac reports; align
   Windows and Mac timestamps per cycle (both clocks are Europe/Istanbul).
2. If the mouse still arrives more than ~1 s after the keyboard on Mac → Windows after the Mac patch,
   measure it over several cycles and decide whether `HOST_CHANGE_DEFER_TTL` (10 s) needs changing.
3. Fill the verification matrix.

## Verification matrix

| # | Direction | Keyboard moved | Mouse moved | Log evidence (side, time) | By / when |
|---|---|---|---|---|---|
| 1 | Windows → Mac | | | | |
| 2 | Mac → Windows | | | | |
| 3 | Windows → Mac, quick return (1–2 s after arrival) | | | | |
| 4 | Mac → Windows, quick return | | | | |
| 5 | 5 cycles with 5–10 s pauses | | | | |
| 6 | Sleeping mouse, press 1, wake within 10 s | | | | |

## Log excerpts

### 2026-10-03/04 stock 1.5.4 on Windows (evidence for the root cause)

Full extracted timelines: `docs/timeline-2026-10-03-stock-1.5.4.txt`, `docs/timeline-2026-10-04-baseline-stock-1.5.4.txt`.

```text
04:49:00  HostChangeEvent target_host=0 → Writing to pid=0xB023: 11ff0a1f00…  (both leave for the Mac)
04:49:13  ENUM present=['0xb35b']            keyboard is back on Windows
04:49:16  'MX Keys' reconnected              (+3 s: backoff step)
04:49:28  HostChangeEvent target_host=1 → Dropping write to pid=0xB023: device disconnected
04:49:36  HostChangeEvent target_host=0 → Dropping write to pid=0xB023: device disconnected
04:49:50  HostChangeEvent target_host=0 → Dropping write to pid=0xB023: device disconnected
04:50:02  ENUM present=['0xb023','0xb35b']   mouse is back on Windows
04:50:31  'MX Master 3' reconnected          (+29 s: backoff step)
```

```text
00:12:42  ENUM present=['0xb35b']  → 'MX Keys' reconnected (fresh process, no backoff yet)
00:12:48  ENUM present=['0xb023','0xb35b'] → 'MX Master 3' reconnected   (mouse trailed the keyboard by 6 s)
00:24:42  'MX Master 3' disconnected        (mouse left Windows 2 s before the keyboard press)
00:24:44  HostChangeEvent target_host=0 → Dropping write to pid=0xB023: device disconnected
```

### Mac (to be appended by [Mac])

## Messages

### 2026-10-04 00:45 [Windows]

Root cause found in `gateway/hid_gateway.py` reconnect backoff (details in README and
`docs/root-cause-analysis.md`). Patched build `1.5.4+reconnect.2` is installed and autostarting on
Windows; stock exe and Startup entry are backed up and the rollback script was exercised end to end.
Both devices have been on the Mac since 00:24:44, so no live switch has been observed with the new
build yet.

For the Mac: please apply the source-only patch as described in `mac/APPLY.md`, restart the service
and append your log excerpt here. Questions I cannot answer from Windows: the exact service log path
and argument list under `brew services`, and whether `HidGatewayBLE` shows `BLE notify subscribed`
after each reconnect. Do not change Karabiner or Options+ settings for this.
