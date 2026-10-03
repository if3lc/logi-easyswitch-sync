# Applying the patch on macOS (Homebrew install)

The Mac runs stock CleverSwitch 1.5.4 from the `mikalaibarysevich/cleverswitch` tap as a
`brew services` daemon. The reconnect bug lives in `gateway/hid_gateway.py`, which the macOS
`HidGatewayBLE` inherits, so the same source patch applies. Nothing here touches Karabiner-Elements or
Logi Options+.

## 1. Locate the installed package

```bash
brew --prefix cleverswitch
PKG=$(brew --prefix cleverswitch)/libexec/lib/python3.*/site-packages/cleverswitch
ls -d $PKG
# fallback: $(brew --prefix cleverswitch)/libexec/bin/python -c 'import cleverswitch,os;print(os.path.dirname(cleverswitch.__file__))'
```

Confirm it is 1.5.4: `cleverswitch --version` (or `$(brew --prefix cleverswitch)/bin/cleverswitch --version`).

## 2. Dry-run, then apply

Copy `patches/cleverswitch-1.5.4-reconnect-src-only.patch` from this repository to the Mac. Its paths
are `a/src/cleverswitch/...`, so run `patch` from the `site-packages` directory with `-p2`:

```bash
cd "$(dirname "$PKG")"            # the site-packages directory that contains cleverswitch/
patch -p2 --dry-run < ~/cleverswitch-1.5.4-reconnect-src-only.patch
patch -p2 < ~/cleverswitch-1.5.4-reconnect-src-only.patch
find cleverswitch -name '__pycache__' -type d -exec rm -rf {} +   # drop stale bytecode
```

Six files change: `cli/cli_module.py`, `discovery/discovery.py`, `event/write_event.py`,
`gateway/hid_gateway.py`, `hidpp/transport.py`, `subscriber/host_change_subscriber.py`.

Alternative: clone this repository, `cd cleverswitch` and use upstream's
`scripts/mac/install_from_sources.sh` (set `SETUPTOOLS_SCM_PRETEND_VERSION=1.5.4+reconnect.2` first,
the subtree has no git metadata). A plain `brew upgrade` would overwrite a patched site-packages, so
pin the formula (`brew pin cleverswitch`) or expect to re-apply.

## 3. Restart and check

```bash
brew services restart cleverswitch
brew services info cleverswitch          # shows the plist, log path and whether it is running
```

The reported version string does not change (metadata is untouched by `patch`); confirm the patch is
live with:

```bash
grep -n "def wake" "$PKG/gateway/hid_gateway.py"
grep -n "HOST_CHANGE_DEFER_TTL" "$PKG/subscriber/host_change_subscriber.py"
```

If the service does not log at DEBUG level, add `-v` (or `-vv`, cheap after the patch) and optionally
`--log-file ~/Library/Logs/cleverswitch.log` to the `ProgramArguments` in the plist that
`brew services info` points at, then restart the service. Input Monitoring permission must still be
granted to the Python binary the service runs.

## 4. What to look for in the Mac log

After a switch away and back:

```text
Device disconnected pid=0xB023
Reconnect wait interrupted for pid=0xB023: device visible      <- new: the sweep woke the gateway
Opened bluetooth path=...
'MX Master 3' reconnected
BLE notify subscribed pid=0xB023                                <- existing BLE path, should still appear
```

A press while the mouse is not open yet:

```text
Deferring write to pid=0xB023 for up to 10.0s: device disconnected
Device pid=0xB023 is back; deferred write goes out in 1.0s unless it turns stale
Sending deferred write to pid=0xB023 (8.7s before expiry)
```

`Discarding deferred write ... stale, the source device is back on this host` means the user already
switched back; that is the intended safety rule, not an error.

## 5. Report back

Append to `HANDOFF.md` under "Log excerpts / Mac" and "Messages": the service's argument list and log
path, the version/grep check output, and one excerpt per verification cycle with timestamps so the
Windows side can align them.
