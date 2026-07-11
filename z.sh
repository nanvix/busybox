#!/usr/bin/env bash
# Copyright(c) The Maintainers of Nanvix.
# Licensed under the MIT License.

# Thin wrapper that delegates to the nanvix-zutil CLI.
# Self-bootstraps nanvix-zutil into .nanvix/venv/ if it is not already installed.

set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
VERSION_FILE="$REPO_ROOT/.zutils-version"
if [ ! -f "$VERSION_FILE" ]; then
    echo "Error: $VERSION_FILE not found." >&2
    exit 1
fi
RAW_ZUTIL_VERSION="$(tr -d '[:space:]' <"$VERSION_FILE")"
ZUTIL_VERSION="${RAW_ZUTIL_VERSION#v}"
VENV="$REPO_ROOT/.nanvix/venv"

# Resolve venv layout (bin/ vs Scripts/) based on what exists on disk.
# Can be called before venv creation to initialize default paths; call it
# again after venv creation to pick up the actual layout.
function _resolve_venv_paths() {
    if [ -d "$VENV/Scripts" ]; then
        VENV_BIN="$VENV/Scripts/nanvix-zutil.exe"
        VENV_PYTHON="$VENV/Scripts/python.exe"
    else
        VENV_BIN="$VENV/bin/nanvix-zutil"
        VENV_PYTHON="$VENV/bin/python"
    fi
}
_resolve_venv_paths
ZUTIL_GLOBAL_VERSION="$(nanvix-zutil --version 2>/dev/null || true)"

function bootstrap() {
    # Pin nanvix-zutil version for reproducible bootstrapping.
    echo "nanvix-zutil not found -- bootstrapping nanvix-zutil==${ZUTIL_VERSION}..." >&2

    local python
    if command -v python3.12 &>/dev/null; then
        python="python3.12"
    elif command -v python3 &>/dev/null \
        && python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 12))'; then
        python="python3"
    else
        echo "Error: Python 3.12 or newer is required by nanvix-zutil." >&2
        exit 1
    fi

    WHEEL_URL="https://github.com/nanvix/zutils/releases/download/v${ZUTIL_VERSION}/nanvix_zutil-${ZUTIL_VERSION}-py3-none-any.whl"
    if [ -d "$VENV" ]; then
        "$python" -m venv --clear "$VENV"
    else
        "$python" -m venv "$VENV"
    fi
    # Re-resolve paths now that the venv exists (Scripts/ vs bin/).
    _resolve_venv_paths
    "$VENV_PYTHON" -m pip install --quiet "nanvix-zutil[lint] @ ${WHEEL_URL}"
}

# Prefer the venv copy if it exists; otherwise use the global install.
BIN=""
if [ ! -d "$VENV" ] && [ -z "$ZUTIL_GLOBAL_VERSION" ]; then
    bootstrap
    BIN="$VENV_BIN"
elif [ -x "$VENV_BIN" ]; then
    VENV_VERSION="$("$VENV_BIN" --version 2>/dev/null || true)"
    if [ "$VENV_VERSION" != "nanvix-zutil ${ZUTIL_VERSION}" ]; then
        echo "Warning: venv nanvix-zutil version mismatch. Expected ${ZUTIL_VERSION}, found ${VENV_VERSION}. Re-bootstrapping..." >&2
        bootstrap
    fi
    BIN="$VENV_BIN"
elif [ -d "$VENV" ] && ! command -v nanvix-zutil &>/dev/null; then
    echo "Warning: incomplete venv detected (binary missing). Re-running bootstrap..." >&2
    bootstrap
    BIN="$VENV_BIN"
else
    BIN="nanvix-zutil"
    if [ "$ZUTIL_GLOBAL_VERSION" != "nanvix-zutil ${ZUTIL_VERSION}" ]; then
        echo "Warning: nanvix-zutil global install does not match expected version. Expected ${ZUTIL_VERSION}, found ${ZUTIL_GLOBAL_VERSION}." >&2
        bootstrap
        BIN="$VENV_BIN"
    fi
fi

# On Windows (Git Bash / MSYS2) the venv's python.exe is locked while it runs,
# so the Python distclean command cannot delete it.  Run without exec so the
# shell can remove the venv after the interpreter exits.
if [[ "${1:-}" == "distclean" ]]; then
    "$BIN" "$@"
    EC=$?
    if [ -d "$VENV" ]; then
        rm -rf "$VENV" 2>/dev/null || true
    fi
    exit $EC
fi

exec "$BIN" "$@"
