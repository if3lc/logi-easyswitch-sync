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
- Mac: Karabiner-Elements Ctrl+H/J/K/L mappings must stay. CleverSwitch is **not** a Homebrew install
  there (the formula wanted Xcode 27.0): it is the v1.5.4 release binary at `~/.local/bin/cleverswitch`
  run by the user LaunchAgent `com.user.cleverswitch`, log `/tmp/cleverswitch.err.log`, Input Monitoring
  granted to that binary. Corrected by [Mac] on 2026-10-04 01:33; details in `mac/README.md`.
- Windows: Logi Options+ agent runs alongside; leave it.

## Status

| Side | Build | Autostart | Verified |
|---|---|---|---|
| Windows | `1.5.4+reconnect.2` (this repo, `windows/dist`) | Startup folder VBS, `-vv --log-file` | unit tests, build, start, rollback round trip, and **live: 8/8 Windows → Mac presses moved both devices, 12/12 reconnects opened in the same second, stale-check prevented one bounce** (00:38–01:03, see excerpt) |
| Mac | `1.5.4+fastreconnect` (local PyInstaller build of upstream v1.5.4 + `patches/mac-reconnect-backoff-deferred-write.patch`, **not** the repository patch — see `mac/README.md` §3) | LaunchAgent `com.user.cleverswitch`, no `-v` | 473 unit tests, build, install, Input Monitoring re-grant; **live 01:01–01:27: 6/6 Mac → Windows presses wrote to the mouse in the same second and both devices left together, incl. a return 3 s after the keyboard arrived; every reconnect subscribed BLE notify in the same second** |

## Open tasks

### Mac
1. ~~Apply `patches/cleverswitch-1.5.4-reconnect-src-only.patch`~~ — done differently: the Mac runs
   its own smaller patch (`patches/mac-reconnect-backoff-deferred-write.patch`), see [Mac] 2026-10-04 01:33.
   Still open: rebuild the Mac binary from this repository's `cleverswitch/` tree so both machines run
   the same code (needs a fresh Input Monitoring grant, `mac/README.md` §5).
2. Verbose logging: the Mac build has no log rotation, and `-v` logs every mouse report (~3 MB in
   30 min), so the LaunchAgent runs at INFO. The Mac patch logs its hold/flush path at INFO, so the
   relevant lines are visible anyway. Enable `-v` only for a test session (`mac/README.md` §1).
3. Rows 2 and 4 done from the Mac log (matrix); rows 5 and 6 still need a deliberate run.
4. Service facts reported in `mac/README.md` §1 and the [Mac] message below.

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
| 2b | Mac → Windows, Mac patched | yes | yes, 6/6 | Mac 01:02:45, 01:03:12, 01:04:15, 01:17:26, 01:18:00, 01:26:12: `Writing to pid=0xB023: 11ff0a1f01…` in the same second as the press, both `disconnected` within 1 s; pointer movement confirmed by the user | [Mac] 2026-10-04 01:33 (log + user) |
| 3 | Windows → Mac, quick return (1–2 s after arrival) | yes | yes | Windows 00:41:36, 01:02:48 | [Windows] 2026-10-04 (log) |
| 4 | Mac → Windows, quick return | yes | yes | Mac 01:03:12: press 3 s after `'MX Keys' reconnected` (01:03:09), mouse open since 01:02:49 → write same second, both left 01:03:12/13. Also 01:18:00, 17 s after arrival. No 1–2 s return was attempted on the Mac yet | [Mac] 2026-10-04 01:33 (log + user) |
| 5 | 5 cycles with 5–10 s pauses | | | 8 Windows → Mac presses in 00:38–01:03 all moved both; Mac side 6 Mac → Windows presses 01:02–01:26 all moved both, pauses were 1–8 min | still needs one deliberate 5-cycle run with both logs open |
| 6 | Sleeping mouse, press 1, wake within 10 s | | | | not run yet on either side. Note: the Mac build's held write expires after 5 s, not 10 s |

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

### 2026-10-03/04 stock 1.5.4 on the Mac (INFO log; same blind window as on Windows)

Full extracted timeline: `docs/timeline-2026-10-04-mac.txt` (covers 2026-10-03 04:31 → 2026-10-04 01:28).

```text
23:21:34  Sending host change to 'MX Master 3' -> host 2 → both disconnected 23:21:34/35
23:21:50  'MX Keys' reconnected
23:22:07  'MX Master 3' reconnected            (+17 s after the keyboard: backoff step)
23:53:16  'MX Master 3' reconnected
23:53:20  'MX Master 3' disconnected           (mouse bounced; no Mac write)
23:53:47  'MX Keys' reconnected
23:53:52  'MX Master 3' reconnected            (+32 s after the bounce)
```

Stock build with `-v` (2026-10-03 04:42, the only verbose stock sample on the Mac):

```text
04:42:33  HostChangeEvent target_host=1 → Writing to pid=0xB023: 11ff0a1f01…  → echo 11ff0a1f00… → both disconnected
04:42:40  'MX Keys' reconnected                (mouse still on Windows: Windows had dropped its write)
04:42:45  HostChangeEvent target_host=0 → Dropping write to pid=0xB023: device disconnected
04:42:47  HostChangeEvent target_host=1 → Dropping write to pid=0xB023: device disconnected
04:43:40  HostChangeEvent target_host=0 → Dropping write to pid=0xB023: device disconnected
04:44:01  'MX Master 3' reconnected / 'MX Keys' reconnected
```

### 2026-10-04 00:10–00:55 patched Mac binary without a valid Input Monitoring grant

The replaced binary has a new code hash; the old TCC entry no longer matched. Nothing was opened for
45 minutes and nothing was logged at INFO. With `-v` (00:55:58 instance):

```text
00:56:06  Failed to connect to HID device pid=0xB023: hid_open_path: … (0xE00002E2) (iokit/common) not permitted
```

Toggling the entry off/on did not fix it (00:58:14, both pids `not permitted`); removing and re-adding
the binary did (01:01:03, both `Opened bluetooth path=…`). The user's "mouse stays on the Mac" reports
between 00:30 and 01:00 fall in this window and are explained by it, not by the patch.

### 2026-10-04 01:01–01:27 patched `1.5.4+fastreconnect` on the Mac (live, user-driven, `-v`)

No ERROR/WARNING lines. Each Mac → Windows press:

```text
01:02:45  HostChangeEvent target_host=1 → Sending host change to 'MX Master 3' -> host 2
01:02:45  Writing to pid=0xB023: 11ff0a1f01…   → 'MX Keys' disconnected, 'MX Master 3' disconnected (same second)
01:03:12  same pattern, 3 s after 'MX Keys' reconnected (01:03:09)      ← quick return
01:04:15  same pattern
01:17:26  same pattern
01:18:00  same pattern, 17 s after 'MX Keys' reconnected (01:17:43)
01:26:12  same pattern
```

Reopen after each return (`Opened bluetooth` → `reconnected` → `BLE notify subscribed`, all within 1 s):

```text
01:17:40  Opened bluetooth path=b'DevSrvsID:4295059213'
01:17:41  BLE notify subscribed pid=0xB023 / 'MX Master 3' reconnected
01:17:42  Opened bluetooth path=b'DevSrvsID:4295059229'
01:17:43  BLE notify subscribed pid=0xB35B / 'MX Keys' reconnected → Enabling analytics for CID 0x00D1..D3 (acked, sw_id=14)
```

The Mac log has no enumeration dump (`-v`), so "enumerable → opened" is not measurable there; the Mac
patch bounds it at 2 s. The held-write path never fired: the mouse was always open before the next press.

Mouse-alone movements seen from the Mac: 01:02:49 `'MX Master 3' reconnected` with no Mac write before
it (the user confirmed using the mouse's own channel button during this period, see Messages).

### Mac (further entries appended below by [Mac])

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

### 2026-10-04 01:33 [Mac]

Mac side is done and live-verified; everything is recorded in `mac/README.md`, `mac/tools/`,
`patches/mac-reconnect-backoff-deferred-write.patch` and `docs/timeline-2026-10-04-mac.txt`.

What was changed on the Mac:
- The daemon binary at `~/.local/bin/cleverswitch` is now a local PyInstaller build
  `1.5.4+fastreconnect` (upstream v1.5.4 + the Mac patch). The stock v1.5.4 binary is backed up locally.
  Plist, LaunchAgent, Karabiner and Options+ settings are unchanged.
- The Mac patch is **not** the repository patch; it was written independently the same night, before
  this repository existed, and was left in place because the Mac was verified with it. Differences
  are tabled in `mac/README.md` §3: backoff cap 2 s instead of discovery `wake()` + 5 s; parked write
  inside the gateway (any write, latest wins, 5 s TTL, flushed by the reader thread right after
  reconnect) instead of `WriteEvent.defer_ttl` 10 s + 1 s grace + `discard_if` stale check; no
  `--log-file`. I did not merge it into `cleverswitch/`, which already carries your version of the same
  fix; converging the Mac on `cleverswitch/` is the open item (rebuild + fresh Input Monitoring grant).
- Input Monitoring had to be removed and re-added for the new binary; toggling was not enough. Expect
  the same after any future rebuild (`mac/README.md` §5).

Answers to your two questions:
1. Service log path and argument list: not `brew services`. LaunchAgent
   `~/Library/LaunchAgents/com.user.cleverswitch.plist`, `ProgramArguments = [/Users/if3lc/.local/bin/cleverswitch]`
   (no `-v`), `RunAtLoad`/`KeepAlive` true, stderr → `/tmp/cleverswitch.err.log` (the application log,
   INFO, no rotation), stdout → `/tmp/cleverswitch.out.log` (empty). `-v` was used only for the 00:55–01:28
   test window and removed again at 01:28:16. `BLE notify subscribed` appears in the same second as
   every `reconnected` line after the first start (7/7 per device); on the very first start after the
   permission change it took 35 s (01:01:03 → 01:01:39), most likely the Bluetooth permission prompt.
2. Writes to `0xB023` at 00:53:44 and 00:55:45: **none**. Between 00:10:49 and 00:55:49 the Mac daemon
   had no valid Input Monitoring grant and never opened either device, so it issued no writes at all
   (nothing in the log for that window except start/stop). The same holds for the 01:02:49 mouse-alone
   return to the Mac. The user says he switched the mouse with its own Easy-Switch button during that
   period because the relay was not working, which accounts for all three. Nothing in the Mac log
   points at Options+ Flow.

Remaining from the Mac side: matrix rows 5 (deliberate 5-cycle run) and 6 (sleeping mouse; note the
Mac build's held write expires after 5 s, not 10 s), and the convergence rebuild. Ready to run rows 5
and 6 whenever you are; I will append the Mac excerpts here.
