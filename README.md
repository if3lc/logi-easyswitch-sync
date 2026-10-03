# logi-easyswitch-sync

Reliable Easy-Switch synchronisation for a Logitech **MX Keys** (original) and **MX Master 3**
(original) shared between a Mac and a Windows PC over Bluetooth, built on
[CleverSwitch](https://github.com/MikalaiBarysevich/CleverSwitch) 1.5.4.

Press Easy-Switch **1** or **2** on the keyboard and both devices move together. Upstream
CleverSwitch does exactly this, but after a round trip it is blind to the returning mouse for up to
29 seconds, and every press inside that window leaves the mouse on the old computer. This repository
carries a patched build that closes the window, the tooling to install, log, verify and roll back on
Windows, the same patch for the Mac side, and a hand-off file for the two machines' operators.

| Side | State |
|---|---|
| Windows | `1.5.4+reconnect.2` installed, autostarts, logging to a rotating file |
| macOS | stock 1.5.4 via Homebrew, patch pending — see [HANDOFF.md](HANDOFF.md) and [mac/APPLY.md](mac/APPLY.md) |

## The setup this was built for

| Item | Value |
|---|---|
| Keyboard | MX Keys (original, not S), Bluetooth HID PID `0xB35B` |
| Mouse | MX Master 3 (original, not 3S), Bluetooth HID PID `0xB023` |
| Easy-Switch channel 1 | Mac, on both devices (0-based host index 0) |
| Easy-Switch channel 2 | Windows 11, on both devices (host index 1) |
| Connection | Direct Bluetooth on both computers, no receiver |
| Windows coexistence | Logi Options+ agent running; it is not touched |
| macOS coexistence | Karabiner-Elements with Ctrl+H/J/K/L mappings; they must stay |

Logitech's own Enhanced Easy-Switch does not cover the original MX Keys, hence CleverSwitch.

## The problem

Switching worked only intermittently: the keyboard always moved, the mouse sometimes stayed behind,
most often when switching back soon after arriving. Waiting a while before switching made it work.

## Root cause

`HidGateway` reopens a device that dropped its Bluetooth link with an exponential backoff of
1, 2, 4, 8, 16, 30, 30 … seconds, and nothing interrupts that wait when the device comes back. In the
-vv log every `reconnected` line lands exactly on one of those steps, long after Windows could already
open the device:

| Device enumerable again | CleverSwitch said `reconnected` | Lag |
|---|---|---|
| 04:46:30 keyboard | 04:46:33 | 3 s |
| 04:48:28 keyboard, 04:48:29 mouse | 04:48:46 / 04:48:49 | 18 / 20 s |
| 04:49:13 keyboard | 04:49:16 | 3 s |
| 04:50:02 mouse | 04:50:31 | 29 s |
| 04:53:01 both | 04:53:11 | 10 s |

A press inside the lag produced `Dropping write to pid=0xB023: device disconnected`: the keyboard
switched natively, the mouse never got its command. Rapid back-and-forth switching made the window
grow, which is why it looked random. The Mac runs the same class (`HidGatewayBLE` inherits it), so the
"press 2 on the Mac, only the keyboard comes" symptom has the same cause; upstream issue
[#121](https://github.com/MikalaiBarysevich/CleverSwitch/issues/121) describes it on macOS.

Full write-up with log excerpts: [docs/root-cause-analysis.md](docs/root-cause-analysis.md).

## What the patch changes

Unified diff against upstream v1.5.4: [patches/cleverswitch-1.5.4-reconnect.patch](patches/cleverswitch-1.5.4-reconnect.patch)
(source + tests) and [patches/cleverswitch-1.5.4-reconnect-src-only.patch](patches/cleverswitch-1.5.4-reconnect-src-only.patch)
(source only, for patching an installed package).

1. **The discovery sweep wakes gateways.** `discovery.py` already enumerates HID devices twice a
   second; it now calls `HidGateway.wake()` for a known pid that is enumerable while its gateway is
   disconnected, so a returning device is opened within one sweep. The backoff cap drops from 30 s to
   5 s as a safety net; it only applies while the device is genuinely absent.
2. **Deferred host change.** When the Easy-Switch press lands while the peer device is not open yet,
   the host-change write is parked instead of dropped (`WriteEvent.defer_ttl`, 10 s) and sent 1 s after
   the device reconnects. Only the newest target is kept; the keyboard that reported the press never
   gets a parked write; the parked write is discarded if the source keyboard is back on this host by
   then (`WriteEvent.discard_if`), so a quick return trip is never bounced. Nothing retries blindly or
   forever. Side effect: a sleeping mouse that is woken within 10 s of the press follows the keyboard.
3. **`--log-file FILE`, `--log-max-mb N`, `--log-backups N`.** Size-rotated log mirror so the hidden
   daemon can run with `-vv` indefinitely.
4. **Quieter `-vv`.** The enumeration dump is logged only when it changes (it was ~1.3 KB twice a
   second, 48 MB in 12 hours).

Test suite: 493 tests pass, 96 % coverage, `ruff format --check` and `ruff check` clean.

## Repository layout

```text
cleverswitch/            patched CleverSwitch 1.5.4 source tree (cross-platform; tests included)
patches/                 the same change as unified diffs against upstream v1.5.4
windows/dist/            prebuilt cleverswitch.exe (Python 3.14, PyInstaller onefile) + SHA256SUMS.txt
windows/tools/           install.ps1, restart_cleverswitch.ps1, rollback_to_stock.ps1,
                         analyze_log.py, probe_reconnect.py
mac/APPLY.md             how to apply the patch to the Homebrew install
docs/                    root-cause analysis and extracted log timelines
HANDOFF.md               running coordination file between the Windows and Mac operators
LICENSE                  GPL-3.0-or-later (inherited from upstream)
```

## Windows

### Install the prebuilt exe

Per-user install, no elevation. From a PowerShell prompt in the repository:

```powershell
powershell -ExecutionPolicy Bypass -File .\windows\tools\install.ps1
```

The script verifies the exe (`cleverswitch.exe --version`), stops any running instance, backs up the
current exe and Startup entry under `%LOCALAPPDATA%\Programs\CleverSwitch\backup`, copies the new exe,
writes `run_cleverswitch.vbs` into the user's Startup folder so the daemon starts hidden at logon with
`-vv --log-file "...\logs\cleverswitch.log"`, and launches it through that same Startup entry.

Check the checksum first if you like:

```powershell
Get-FileHash .\windows\dist\cleverswitch.exe -Algorithm SHA256; Get-Content .\windows\dist\SHA256SUMS.txt
```

### Build from source

Needs Python 3.14 (the version the stock release was built with) and [uv](https://docs.astral.sh/uv/).
`hidapi.dll` 0.15.0 sits at `cleverswitch/hidapi.dll`; `hid_send_output_report` (the Bluetooth write
path) needs 0.15 or newer.

```powershell
cd cleverswitch
uv venv --python 3.14 .venv
uv pip install --python .venv\Scripts\python.exe -e ".[dev]" pyinstaller ruff
Copy-Item hidapi.dll .venv\Scripts\            # transport.py adds <prefix>\Scripts to the DLL search path
.venv\Scripts\python.exe -m pytest              # 90 % coverage gate from pyproject
$env:SETUPTOOLS_SCM_PRETEND_VERSION = "1.5.4+reconnect.2"   # no git metadata in this subtree
uv pip install --python .venv\Scripts\python.exe .
.venv\Scripts\pyinstaller.exe --noconfirm --onefile --name cleverswitch --paths src --hidden-import yaml --copy-metadata cleverswitch --add-binary "hidapi.dll;." --distpath build\dist --workpath build\work --specpath build src\cleverswitch\__main__.py
build\dist\cleverswitch.exe --version           # cleverswitch 1.5.4+reconnect.2 (hidapi 0.15.0, Windows)
```

Use absolute Windows-style paths for `--add-binary` if you build from Git Bash; MSYS path
conversion mangles the `;.` suffix otherwise.

### Logs, verification, rollback

```powershell
# timeline of enumerations, presses, writes, deferrals, (re)connects
python .\windows\tools\analyze_log.py "$env:LOCALAPPDATA\Programs\CleverSwitch\logs\cleverswitch.log"

# stop + relaunch exactly as at logon
powershell -ExecutionPolicy Bypass -File .\windows\tools\restart_cleverswitch.ps1

# back to the untouched upstream exe and Startup entry saved by install.ps1
powershell -ExecutionPolicy Bypass -File .\windows\tools\rollback_to_stock.ps1
```

Two `cleverswitch.exe` processes are normal: the PyInstaller onefile bootstrapper and its child.

## macOS

See [mac/APPLY.md](mac/APPLY.md): locate the Homebrew-installed package, `patch -p2 --dry-run` the
source-only diff inside its `site-packages`, apply, `brew services restart cleverswitch`, then look for
`Reconnect wait interrupted`, `Deferring write`, `Sending deferred write` in the service log.

## Verification protocol

With both daemons running and their logs open:

1. Both devices on Windows, press **1** on the keyboard: both move to the Mac. Windows log shows
   `Writing to pid=0xB023: 11ff0a1f00…` followed by `'MX Master 3' disconnected`.
2. On the Mac press **2**: both move to Windows. The `reconnected` line for each device must be in
   the same or the next second as its `ENUM present` change (it used to be 3–29 s later).
3. Quick return: 1–2 s after arriving on Windows press **1** again. If the mouse was not open yet the
   log shows `Deferring write to pid=0xB023 …`, `… is back; deferred write goes out in 1.0s`,
   `Sending deferred write`, and the mouse arrives on the Mac.
4. Repeat the cycle five times with 5–10 s pauses. The mouse must move the pointer on the target
   computer every time; a log line alone does not count.
5. Sleeping mouse: leave the mouse idle for a few minutes, press **1**, then move the mouse within
   10 s. It should follow to the Mac.

Record outcomes in the matrix in [HANDOFF.md](HANDOFF.md).

## Known limitations

- Until the Mac side is patched, the Mac → Windows direction still depends on the Mac's blind window.
- A parked host change expires after 10 s; a mouse that takes longer to arrive stays behind as before.
- Very rarely (press 1 on Windows, press 2 on the Mac within a few seconds, and the mouse reconnects to
  Windows more than 1 s before the keyboard) the parked command can send the mouse back; the log shows
  it as `Sending deferred write`.
- Logi Options+ talks to the keyboard on the same HID collection (responses with `sw_id=2`/`11` appear
  in the log). No interference was observed; its settings were left alone.
- The daemon is killed, not signalled, on Windows restarts. The keyboard uses analytics reporting for
  the Easy-Switch keys, so nothing needs to be undiverted and the physical 1/2 keys keep working
  without CleverSwitch running.

## Upstream

Not submitted upstream yet. The change is deliberately contained (6 source files) so it could become a
pull request against CleverSwitch; it would resolve issue #121. One unrelated upstream nit found on the
way: `HidGateway` names its stop event `_stop`, shadowing `threading.Thread._stop`, which breaks
`join()`/`is_alive()` on Python ≤ 3.12 (upstream CI and the release use 3.14, where it is harmless).

## License

GPL-3.0-or-later, inherited from CleverSwitch (© Mikalai Barysevich and contributors). `hidapi.dll`
is from [libusb/hidapi](https://github.com/libusb/hidapi) 0.15.0 under its own licence.
