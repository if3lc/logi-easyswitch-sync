#!/bin/bash
# Print the Karabiner-Elements settings this setup depends on: the CGEventTap fallback flag, the
# per-device ignore flags of the selected profile and the complex-modification rule names.
set -euo pipefail
python3 - <<'PY'
import json, os
p = os.path.expanduser("~/.config/karabiner/karabiner.json")
d = json.load(open(p))
print("file:", p)
print("global:", json.dumps(d.get("global")))
prof = next(x for x in d["profiles"] if x.get("selected"))
print("selected profile:", prof["name"])
for dev in prof.get("devices", []):
    print("  device", json.dumps(dev["identifiers"], sort_keys=True), "ignore =", dev.get("ignore"))
for r in prof.get("complex_modifications", {}).get("rules", []):
    print("  rule:", r["description"])
PY
