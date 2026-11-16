#!/usr/bin/env bash
# SelfiCamera launcher: creates/updates .venv only when requirements change, then starts the app.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
PY="$VENV_DIR/bin/python"
STAMP="$VENV_DIR/.selficamera-deps"
export UV_LINK_MODE=copy

log() { echo "[SelfiCamera] $*" >&2; }

if [ ! -x "$PY" ] || ! "$PY" -c "import sys" >/dev/null 2>&1; then
    log "Creating virtual environment…"
    rm -rf "$VENV_DIR"
    if command -v uv >/dev/null 2>&1; then
        uv venv --python 3.12 "$VENV_DIR" >/dev/null 2>&1 || uv venv "$VENV_DIR" >/dev/null
    else
        python3 -m venv "$VENV_DIR"
    fi
fi

exec 9>"$VENV_DIR/.install.lock"
flock 9
WANT="$(cat "$SCRIPT_DIR/requirements.txt" "$SCRIPT_DIR/requirements-optional.txt" 2>/dev/null | sha256sum | cut -d' ' -f1)"
if [ ! -f "$STAMP" ] || [ "$(cat "$STAMP")" != "$WANT" ]; then
    log "Installing dependencies (first run or update)…"
    if command -v uv >/dev/null 2>&1; then
        uv pip install --quiet --python "$PY" -r "$SCRIPT_DIR/requirements.txt"
        uv pip install --quiet --python "$PY" -r "$SCRIPT_DIR/requirements-optional.txt" \
            || log "Optional AI runtime (ai-edge-litert) unavailable on this platform; background effects use basic mode."
    else
        "$PY" -m pip install --quiet --upgrade pip
        "$PY" -m pip install --quiet -r "$SCRIPT_DIR/requirements.txt"
        "$PY" -m pip install --quiet -r "$SCRIPT_DIR/requirements-optional.txt" \
            || log "Optional AI runtime (ai-edge-litert) unavailable on this platform; background effects use basic mode."
    fi
    echo "$WANT" > "$STAMP"
fi
flock -u 9

export PYTHONPATH="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}"
exec "$PY" -m selficamera "$@"
