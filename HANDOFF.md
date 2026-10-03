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
| Windows | `1.5.4+reconnect.2` (this repo, `windows/dist`) | Startup folder VBS, `-vv --log-file` | unit tests, build, start, rollback round trip, and **live: 8/8 Windows → Mac presses moved both devices, 12/12 reconnects opened in the same second, stale-check prevented one bounce** (00:38–01:03, see excerpt) |
| Mac | stock 1.5.4 (Homebrew) | `brew services` | unpatched: on Mac → Windows the mouse trails the keyboard by 1–12 s and twice did not come at all until a later press (see excerpt) |

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
| 1 | Windows → Mac | yes | yes | Windows 00:40:09, 00:52:41, 00:54:07, 01:03:17: write + echo + both disconnect | [Windows] 2026-10-04 (log) |
| 2 | Mac → Windows | yes | late (1–12 s) or missing until a later press | Windows 00:39:04, 00:41:35, 00:53:13, 01:02:51 | [Windows] 2026-10-04 (log); Mac unpatched |
| 3 | Windows → Mac, quick return (1–2 s after arrival) | yes | yes | Windows 00:41:36, 01:02:48 | [Windows] 2026-10-04 (log) |
| 4 | Mac → Windows, quick return | | | | pending Mac patch |
| 5 | 5 cycles with 5–10 s pauses | | | 8 Windows → Mac presses in 00:38–01:03 all moved both | needs a deliberate run after the Mac patch |
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

### 2026-10-04 00:38–01:03 patched 1.5.4+reconnect.2 on Windows (live, user-driven)

Full extracted timeline: `docs/timeline-2026-10-04-live-reconnect2.txt`. No ERROR/WARNING lines.

Reopen latency after the fix (every reconnect, both devices):

```text
00:41:25  ENUM present=['0xb35b'] → Reconnect wait interrupted → 'MX Keys' reconnected      same second
00:41:35  ENUM present=[…,'0xb023'] → Reconnect wait interrupted → 'MX Master 3' reconnected  same second
(12 of 12 reconnects between 00:41 and 01:03 opened in the same second; stock build: 3–29 s)
```

Quick return, 1 s after the mouse arrived (would have been dropped by the stock build):

```text
00:41:35  'MX Master 3' reconnected
00:41:36  HostChangeEvent target_host=0 → Writing to pid=0xB023: 11ff0a1f00…  → echo → both disconnected
01:02:47  'MX Master 3' reconnected
01:02:48  HostChangeEvent target_host=0 → Writing to pid=0xB023: 11ff0a1f00…  → echo → both disconnected
```

Parked write discarded by the stale check, exactly the bounce case it exists for:

```text
01:03:07  HostChangeEvent target_host=0 → Deferring write to pid=0xB023 for up to 10.0s   (mouse still on the Mac)
01:03:08  'MX Keys' disconnected                                                           (keyboard went to the Mac)
01:03:14  keyboard AND mouse reconnected together                                          (user pressed 2 on the Mac)
01:03:14  Device pid=0xB023 is back; deferred write goes out in 1.0s unless it turns stale
01:03:15  Discarding deferred write to pid=0xB023: stale, the source device is back on this host
01:03:17  HostChangeEvent target_host=0 → Writing to pid=0xB023 → both leave               (next press works normally)
```

Expiry path (mouse never came back within 10 s): parked 00:56:24, `Discarding deferred write ... expired 374.2s ago` at 01:02:48.

Mac → Windows arrival gaps measured on Windows (keyboard first, then mouse), i.e. how late the
**Mac** side sends the mouse: +6 s (00:39), +10 s (00:41), +4 s (00:50), +12 s (00:53), +5 s (00:54),
+1 s (01:02), 0 s (01:03). At 01:02:51 and 01:03:02 the keyboard came back alone and the mouse only
followed at 01:03:14 — the Mac-side blind window; this is what the Mac patch should remove.

Unexplained, not caused by the Windows daemon (no write was issued): the mouse connected to Windows
alone at 00:53:44 and left at 00:53:49; connected alone at 00:55:45 (2 s before the keyboard) and
left alone at 00:56:06. Candidates: the mouse's own channel button, or Logi Options+ Flow if it is
enabled on either machine. [Mac], please check whether the Mac log shows writes to `0xB023` at those
times.

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

### 2026-10-04 01:25 [Windows]

Live data arrived after all: the user switched back and forth between 00:38 and 01:03 with the
patched build running. Results are in the "Log excerpts" section and the matrix. Summary: every
Windows → Mac press with the mouse present moved both devices (8/8), including two presses 1 s after
the mouse arrived; all 12 reconnects were opened in the same second they became visible; the parked
write was discarded once by the stale check (01:03:15) in precisely the situation it guards against,
and expired once. The remaining failures are all on the Mac → Windows leg: the mouse trails by 1–12 s
or stays on the Mac until a later press — the unpatched Mac gateway. Priority for [Mac]: apply the
patch, then we rerun rows 2, 4, 5 and 6 of the matrix together.
