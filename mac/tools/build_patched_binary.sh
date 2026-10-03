#!/bin/bash
# Build the Mac CleverSwitch binary that is installed on this Mac: upstream v1.5.4 plus
# patches/mac-reconnect-backoff-deferred-write.patch, as a PyInstaller onefile (same command as
# upstream scripts/mac/build.sh). Needs Homebrew python@3.14 and hidapi.
#
# Usage: mac/tools/build_patched_binary.sh [workdir]      (default: ./build-mac)
# Result: <workdir>/src/dist/cleverswitch
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="${1:-$REPO_DIR/build-mac}"
PATCH="$REPO_DIR/patches/mac-reconnect-backoff-deferred-write.patch"
PYTHON="${PYTHON:-/opt/homebrew/bin/python3.14}"
VERSION="${SETUPTOOLS_SCM_PRETEND_VERSION:-1.5.4+fastreconnect}"

[ -x "$PYTHON" ] || { echo "python 3.14 not found at $PYTHON (brew install python@3.14)"; exit 1; }
[ -e /opt/homebrew/lib/libhidapi.dylib ] || { echo "hidapi missing (brew install hidapi)"; exit 1; }

mkdir -p "$WORK"
cd "$WORK"
if [ ! -d src/.git ]; then
    git clone -q https://github.com/MikalaiBarysevich/CleverSwitch.git src
fi
cd src
git checkout -q v1.5.4
git checkout -q -B fix/reconnect-latency
git apply --check "$PATCH"
git apply "$PATCH"

"$PYTHON" -m venv venv
venv/bin/pip install --quiet --upgrade pip
venv/bin/pip install --quiet "pyyaml>=6.0" "bleak>=0.22,<3" pyobjc-framework-CoreBluetooth \
    pyinstaller pytest pytest-mock pytest-cov ruff

venv/bin/python -m pytest -q
venv/bin/ruff check src tests
venv/bin/ruff format --check src tests

export SETUPTOOLS_SCM_PRETEND_VERSION="$VERSION"
venv/bin/pip install --quiet .
rm -rf build dist
venv/bin/pyinstaller --onefile --name cleverswitch --paths src --hidden-import yaml \
    --copy-metadata cleverswitch src/cleverswitch/__main__.py
dist/cleverswitch --version
echo "built: $WORK/src/dist/cleverswitch"
