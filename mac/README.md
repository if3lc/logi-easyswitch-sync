# macOS side

What the problem looked like on the Mac, what was changed, how the daemon runs, and how to redo it on
a fresh Mac. Everything here was done on 2026-10-03/04 (Europe/Istanbul) on an Apple Silicon Mac
running macOS 27.0.1 (26A434), Homebrew in `/opt/homebrew`, Karabiner-Elements 16.3.0 and
Logi Options+ both running. Devices: MX Keys `0xB35B`, MX Master 3 `0xB023`, direct Bluetooth.

**Important difference from `mac/APPLY.md`:** this Mac does *not* run CleverSwitch from Homebrew and
does *not* run the repository patch. It runs a locally built `1.5.4+fastreconnect` binary with the
smaller `patches/mac-reconnect-backoff-deferred-write.patch`. Details and the reason below.

## 1. How CleverSwitch is installed and run

`brew install cleverswitch` from the `mikalaibarysevich/cleverswitch` tap failed on this machine
(the formula wanted Xcode 27.0, Xcode 26.6 is installed; Xcode was left alone). The stock install was
therefore the official v1.5.4 release archive, exactly as upstream's `docs/Installation.md` describes:

| Item | Value |
|---|---|
| Archive | `cleverswitch_macOS.tar.gz` from the v1.5.4 GitHub release, SHA-256 `9aa2d75b6ab87a0ae4ac3c4a7d8f929d5dc03a166a44b3c0c725edd392f97bc0` |
| Installer | `install.command` from the archive, answered `y` to autostart |
| Binary | `~/.local/bin/cleverswitch` (PyInstaller onefile, arm64, ad-hoc signed) |
| hidapi | `brew install hidapi` → 0.15.0; the binary loads `/opt/homebrew/lib/libhidapi.dylib` through ctypes |
| Daemon | user LaunchAgent `com.user.cleverswitch` written by the installer, **not** `brew services` |
| Plist | `~/Library/LaunchAgents/com.user.cleverswitch.plist` (copy: [`com.user.cleverswitch.plist`](com.user.cleverswitch.plist)) |
| ProgramArguments | `/Users/if3lc/.local/bin/cleverswitch` only — no `-v`, no `--config` |
| RunAtLoad / KeepAlive | `true` / `true` |
| stdout | `/tmp/cleverswitch.out.log` (always empty) |
| stderr = application log | `/tmp/cleverswitch.err.log`, INFO level, no rotation, lost at reboot |
| Config | none (`~/.config/cleverswitch/config.yaml` does not exist); device cache `~/.config/cleverswitch/device_cache.json` |
| Permissions | Input Monitoring granted to `~/.local/bin/cleverswitch` (System Settings → Privacy & Security → Input Monitoring); Bluetooth prompt accepted |

`brew services info cleverswitch` has nothing to report on this Mac. The equivalents are:

```bash
launchctl print gui/$(id -u)/com.user.cleverswitch      # state, pid, arguments, log paths
launchctl kickstart -k gui/$(id -u)/com.user.cleverswitch   # restart
tail -f /tmp/cleverswitch.err.log
```

Two `cleverswitch` processes are normal (PyInstaller bootstrapper and its child).

## 2. What the problem looked like on the Mac

Stock 1.5.4, INFO log, 2026-10-03/04. Every Mac → Windows press was relayed, but after a round trip
the mouse's `reconnected` line trailed the keyboard's by 5–30 s, and a press inside that window
relayed only the keyboard:

```text
23:21:35  'MX Master 3' disconnected         (both left for Windows)
23:21:50  'MX Keys' reconnected              (back on the Mac)
23:22:07  'MX Master 3' reconnected          (+17 s: the mouse had been back for a while)

04:42:40  'MX Keys' reconnected
04:42:45  Sending host change to 'MX Master 3' -> host 1
04:42:45  Dropping write to pid=0xB023: device disconnected   (mouse gateway not open yet)
```

With `-v`, `HidGateway._try_connect` was seen sleeping out its backoff (1, 2, 4, 8, 16, 30, 30 … s)
while the mouse was already connected to the Mac. Same root cause as the Windows side
(`docs/root-cause-analysis.md`); the macOS `HidGatewayBLE` inherits the class unchanged.

## 3. The fix that is installed on the Mac

Source branch: upstream v1.5.4 (commit `17999dc`) plus
[`patches/mac-reconnect-backoff-deferred-write.patch`](../patches/mac-reconnect-backoff-deferred-write.patch)
(`src/cleverswitch/gateway/hid_gateway.py` and its test file only). It is **not** identical to
`patches/cleverswitch-1.5.4-reconnect*.patch`; it was written independently the same night, before this
repository existed, and the Mac was verified with it, so it was left in place. The two patches solve
the same problem in the same place but differently:

| | Mac patch (`1.5.4+fastreconnect`) | Repository patch (`1.5.4+reconnect.2`, Windows) |
|---|---|---|
| Reopen a returning device | `_RECONNECT_BACKOFF_MAX` 30 s → **2 s**; nothing else wakes the gateway | discovery sweep calls `HidGateway.wake()` as soon as the pid is enumerable; cap 30 s → 5 s as safety net |
| Write to a gateway that is between connections | parked **inside the gateway** for any write, single slot (latest wins), TTL **5 s**, flushed by the reader thread right after `_set_connected(True)` (on macOS that is after the BLE notify subscription or its 5 s grace); the parked write also interrupts the backoff | only host changes are parked (`WriteEvent.defer_ttl` = 10 s set by `HostChangeSubscriber`), sent 1 s after reconnect on a timer, discarded if the source keyboard is back on this host (`discard_if`); the keyboard that reported the press never gets a parked write |
| Log lines | `pid=0xB023 not connected yet — holding write for up to 5s until it reconnects`, `pid=0xB023 reconnected — sending held write` (INFO) | `Reconnect wait interrupted …`, `Deferring write …`, `… deferred write goes out in 1.0s …`, `Sending deferred write …` |
| Log file options, quieter `-vv` | not included | included |
| Files changed | 1 source file + 1 test file | 6 source files + 5 test files |
| Tests | 473 pass, 95.9 % coverage, ruff clean | 493 pass, 96 % |

So the log lines listed in `mac/APPLY.md` §4 will **not** appear on this Mac; look for the ones in the
left column. In the live run (section 6) the mouse was always open again before the next press, so the
held-write path was never exercised; the 2 s cap alone was enough.

Converging both machines on the repository tree (`cleverswitch/`) is the sensible next step and is
listed as open in `HANDOFF.md`; it needs a rebuild on the Mac and a fresh Input Monitoring grant
(section 5).

## 4. Build the Mac binary (reproducible)

Needs Homebrew Python 3.14 (`brew install python@3.14`; used 3.14.3) and `hidapi` from Homebrew.
Script: [`tools/build_patched_binary.sh`](tools/build_patched_binary.sh). By hand:

```bash
git clone https://github.com/MikalaiBarysevich/CleverSwitch.git src && cd src
git checkout -b fix/reconnect-latency v1.5.4
git apply ../patches/mac-reconnect-backoff-deferred-write.patch     # paths are a/src/..., -p1
/opt/homebrew/bin/python3.14 -m venv venv
venv/bin/pip install "pyyaml>=6.0" "bleak>=0.22,<3" pyobjc-framework-CoreBluetooth pyinstaller pytest pytest-mock pytest-cov ruff
venv/bin/python -m pytest                      # 90 % coverage gate from pyproject
venv/bin/ruff check src tests && venv/bin/ruff format --check src tests
export SETUPTOOLS_SCM_PRETEND_VERSION=1.5.4+fastreconnect
venv/bin/pip install .
venv/bin/pyinstaller --onefile --name cleverswitch --paths src --hidden-import yaml --copy-metadata cleverswitch src/cleverswitch/__main__.py
dist/cleverswitch --version        # cleverswitch 1.5.4+fastreconnect (hidapi 0.15.0, Darwin)
```

This is upstream's `scripts/mac/build.sh` minus the archive step. The hidapi dylib is not bundled;
the binary keeps loading the Homebrew one.

## 5. Install the binary over the stock one

Script: [`tools/install_patched_binary.sh`](tools/install_patched_binary.sh). It backs up the current
binary next to itself, copies the new one to `~/.local/bin/cleverswitch` (same path, so the plist is
untouched) and restarts the LaunchAgent.

**Input Monitoring must be granted again.** Both binaries are ad-hoc signed, so the TCC grant is bound
to the binary's code hash. After the replacement the log showed, for both devices:

```text
hid_open_path: failed to open IOHIDDevice from mach entry: (0xE00002E2) (iokit/common) not permitted
```

(without `-v` nothing is logged at all — the daemon just never says `reconnected`). Switching the
existing `cleverswitch` toggle off and on in System Settings → Privacy & Security → Input Monitoring
did **not** help (it re-enabled the stale entry). What worked: select `cleverswitch`, remove it with
**–**, add it again with **+** (Cmd+Shift+G, `/Users/<user>/.local/bin/cleverswitch`), then restart the
daemon. After that the first start also waited ~35 s before `BLE notify subscribed` appeared, most
likely the Bluetooth permission prompt for the new binary; every later reconnect subscribed within the
same second.

Rollback: `tools/install_patched_binary.sh <backup>` or by hand

```bash
cp ~/.local/bin/cleverswitch.bak-<stamp> ~/.local/bin/cleverswitch
launchctl kickstart -k gui/$(id -u)/com.user.cleverswitch
```

and re-add Input Monitoring for the restored binary for the same reason.

## 6. Verification on the Mac (2026-10-04, `-v` log, Europe/Istanbul)

Daemon `1.5.4+fastreconnect`, permission re-added, started 01:01:03. The user drove the switches and
confirmed the pointer moved on the target computer each time. Full timeline:
`docs/timeline-2026-10-04-mac.txt`.

| Time | Event on the Mac | Result |
|---|---|---|
| 01:01:03 | both devices opened; `reconnected` 01:01:08; BLE notify up 01:01:39/40 | ready |
| 01:02:45 | press **2** → `Writing to pid=0xB023: 11ff0a1f01…` same second, both `disconnected` 01:02:45 | both moved |
| 01:02:49 | mouse `reconnected` alone, no Mac write before it (user pressed the mouse's own channel button) | — |
| 01:03:09 | keyboard `reconnected` (Windows relayed **1** at 01:03:07) | — |
| 01:03:12 | press **2**, 3 s after the keyboard arrived → write same second, both `disconnected` 01:03:12/13 | quick return OK |
| 01:03:18 | both `reconnected` (Windows discarded its stale parked write at 01:03:15, consistent) | — |
| 01:04:15 | press **2** → write, both `disconnected` same second | both moved |
| 01:11:18/19 | both `reconnected` | — |
| 01:17:26 | press **2** → write, both `disconnected` 01:17:26/27 | both moved |
| 01:17:40–43 | mouse opened 01:17:40, `reconnected` 01:17:41; keyboard opened 01:17:42, `reconnected` 01:17:43 | — |
| 01:18:00 | press **2**, 17 s after arrival → write, both `disconnected` same second | both moved |
| 01:25:03/05 | both `reconnected` | — |
| 01:26:12 | press **2** → write, both `disconnected` 01:26:13 | both moved |
| 01:27:16/17 | both `reconnected`; 01:28:16 daemon restarted without `-v` | — |

6/6 Mac → Windows presses wrote to the mouse in the same second and both devices left together.
`BLE notify subscribed` appeared in the same second as every `reconnected` after 01:01:39 (7/7 per
device). The Mac log has no enumeration dump (`-v`, not `-vv`), so the "enumerable → opened" lag cannot
be measured here; by construction it is ≤ 2 s, and `Opened bluetooth` → `reconnected` was ≤ 1 s every
time. The held-write path (`holding write …`) was not triggered in this run.

Between 00:10:49 and 00:55:49 the same binary ran **without** a valid Input Monitoring grant and opened
nothing; presses in that window are not in the Mac log at all. That, not the patch, was behind the
"mouse stays on the Mac" reports in that window.

## 7. Karabiner-Elements change (made earlier, kept)

Why: CleverSwitch could not open the keyboard's HID++ collection while Karabiner-Elements had it
grabbed (`hid_open_path: … (0xE00002C5) exclusive access and device already open`). The user's
Ctrl+H/J/K/L arrow mappings had to keep working, so instead of disabling the rules the keyboard was
set to *ignored* and Karabiner's CGEventTap fallback was switched on. File:
`~/.config/karabiner/karabiner.json`, selected profile `Main`, Karabiner-Elements 16.3.0.

| Setting | Before | After |
|---|---|---|
| `global.enable_cgeventtap_fallback` | absent | `true` |
| `profiles[Main].devices[]` entry for `vendor_id 1133, product_id 45915, is_keyboard true, is_pointing_device true` (MX Keys) | `ignore: false` | `ignore: true` |
| `profiles[Main].devices[]` entry for `vendor_id 1452, product_id 34304` (Apple Touch Bar) | `ignore: true` | unchanged |
| `complex_modifications.rules` | `Vi Mode [left_control + hjkl]`: Ctrl+H → ←, Ctrl+J → ↓, Ctrl+K → ↑, Ctrl+L → → | unchanged |

Karabiner's daemon log confirmed `event_tap_monitor start (enable_cgeventtap_fallback=true)`. Known
cost of the fallback (upstream: Karabiner-Elements `DEVELOPMENT.md`, "CGEventTap fallback behavior"):
the rules cannot act inside password / Secure Event Input fields, and the tap cannot tell which keyboard
an event came from, so the Ctrl+H/J/K/L rules apply to every keyboard. Pre-change backups of the file
are kept locally by the user (`karabiner-before-test.json`, `karabiner-before-fallback.json`).

## 8. Tools in `mac/tools/`

| Script | Purpose |
|---|---|
| `build_patched_binary.sh` | clone upstream v1.5.4, apply the Mac patch, test, build `dist/cleverswitch` |
| `install_patched_binary.sh [binary]` | back up `~/.local/bin/cleverswitch`, install the given binary, restart the LaunchAgent; prints the Input Monitoring reminder |
| `restart_cleverswitch.sh` | restart the LaunchAgent and show its state |
| `tail_log.sh` | follow `/tmp/cleverswitch.err.log` with the mouse/keyboard HID report spam filtered out |
| `karabiner_status.sh` | print the Karabiner settings this setup depends on |
