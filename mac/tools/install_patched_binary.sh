#!/bin/bash
# Install a CleverSwitch binary over ~/.local/bin/cleverswitch (same path, so the LaunchAgent plist is
# untouched), keep a backup next to it, restart the LaunchAgent. Also used for rollback: pass the
# backup as the argument.
#
# Usage: mac/tools/install_patched_binary.sh <path-to-binary>
set -euo pipefail

NEW="${1:?usage: $0 <binary>}"
TARGET="$HOME/.local/bin/cleverswitch"
LABEL="com.user.cleverswitch"
STAMP="$(date +%Y%m%d-%H%M%S)"

[ -x "$NEW" ] || { echo "not executable: $NEW"; exit 1; }
"$NEW" --version

if [ -e "$TARGET" ]; then
    cp -p "$TARGET" "$TARGET.bak-$STAMP"
    echo "backup: $TARGET.bak-$STAMP ($("$TARGET" --version 2>/dev/null || echo 'version unknown'))"
fi
cp "$NEW" "$TARGET.new"
chmod 755 "$TARGET.new"
mv "$TARGET.new" "$TARGET"
launchctl kickstart -k "gui/$(id -u)/$LABEL"
sleep 3
launchctl print "gui/$(id -u)/$LABEL" | grep -E "state = |pid = " || true
tail -n 3 /tmp/cleverswitch.err.log || true

cat <<MSG

Installed $("$TARGET" --version).
The binary's code hash changed, so macOS Input Monitoring must be granted to it again:
  System Settings -> Privacy & Security -> Input Monitoring: remove 'cleverswitch' (-), add it
  again (+, Cmd+Shift+G, $TARGET), then run mac/tools/restart_cleverswitch.sh.
Toggling the existing entry off/on is not enough. Without the grant the log stays silent (no
'reconnected' lines); with -v it shows 'hid_open_path: ... (0xE00002E2) not permitted'.
MSG
