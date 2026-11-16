#!/usr/bin/env bash
# Remove SelfiCamera's launcher, menu entry, icons, shortcuts and autostart entry.
# Settings (~/.config/selficamera) and downloaded models are kept unless --purge is given.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
CONF="${XDG_CONFIG_HOME:-$HOME/.config}"

bash "$SCRIPT_DIR/run.sh" --exit >/dev/null 2>&1 || true
bash "$SCRIPT_DIR/run.sh" --remove-shortcuts >/dev/null 2>&1 || true
(cd "$SCRIPT_DIR" && .venv/bin/python -c "from selficamera.desktop import ShadowExtensions; ShadowExtensions().exclude(False)") >/dev/null 2>&1 || true
rm -f "$HOME/.local/bin/selficamera" "$DATA/applications/selficamera.desktop" "$CONF/autostart/selficamera.desktop"
rm -f "$DATA/icons/hicolor/scalable/apps/selficamera.svg" "$DATA/icons/hicolor/256x256/apps/selficamera.png"
if [ "${1:-}" = "--purge" ]; then
    rm -rf "$CONF/selficamera" "$DATA/selficamera" "${XDG_STATE_HOME:-$HOME/.local/state}/selficamera"
    echo "Removed settings, models and logs."
fi
command -v update-desktop-database >/dev/null && update-desktop-database "$DATA/applications" 2>/dev/null || true
echo "SelfiCamera uninstalled."
