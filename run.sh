#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/.venv"
export UV_LINK_MODE=copy

# Verify virtual environment integrity
if [ ! -x "$VENV_DIR/bin/python" ] || ! "$VENV_DIR/bin/python" -c "import sys" >/dev/null 2>&1; then
    echo "[SelfiCamera] Virtual environment missing or invalid interpreter. Initializing..."
    rm -rf "$VENV_DIR"
    if command -v uv >/dev/null 2>&1; then
        uv venv --python 3.12 "$VENV_DIR" || uv venv "$VENV_DIR"
    else
        PYTHON_CMD="python3"
        if command -v python3.12 >/dev/null 2>&1; then
            PYTHON_CMD="python3.12"
        fi
        $PYTHON_CMD -m venv "$VENV_DIR"
    fi
fi

# Detect uv or fallback to pip
if command -v uv >/dev/null 2>&1; then
    echo "[SelfiCamera] Ensuring dependencies are up-to-date with uv..."
    uv pip install --link-mode=copy --python "$VENV_DIR/bin/python" -r requirements.txt
else
    echo "[SelfiCamera] Ensuring dependencies are up-to-date with pip..."
    "$VENV_DIR/bin/pip" install --upgrade pip
    "$VENV_DIR/bin/pip" install -r requirements.txt
fi

export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb;wayland}"
export PYTHONPATH="$SCRIPT_DIR:${PYTHONPATH:-}"

echo "[SelfiCamera] Launching SelfiCamera..."
exec "$VENV_DIR/bin/python" -m selficamera "$@"
