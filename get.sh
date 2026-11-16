#!/usr/bin/env bash
# SelfiCamera one-line installer (and updater) for Linux.
#
#   curl -fsSL https://raw.githubusercontent.com/mgmehdiforme/SelfiCamera/main/get.sh | bash
#
# Downloads SelfiCamera to ~/.local/share/selficamera/app, prepares an isolated Python
# environment, downloads the offline AI models and adds SelfiCamera to your app menu.
# Run it again at any time to update. Nothing is installed system-wide and no sudo is used.
# Extra options are passed to install.sh, e.g.:  ... | bash -s -- --with-shortcuts --autostart
set -euo pipefail

REPO="${SELFICAMERA_REPO:-https://github.com/mgmehdiforme/SelfiCamera.git}"
BRANCH="${SELFICAMERA_BRANCH:-main}"
DEST="${SELFICAMERA_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/selficamera/app}"

say() { printf '\033[1m%s\033[0m\n' "$*"; }
die() { printf 'SelfiCamera: %s\n' "$*" >&2; exit 1; }

[ "$(uname -s)" = "Linux" ] || die "SelfiCamera runs on Linux only."
command -v git >/dev/null 2>&1 || die "git is required. Install it with:  sudo apt install git"
command -v curl >/dev/null 2>&1 || die "curl is required. Install it with:  sudo apt install curl"

say "SelfiCamera installer"
if [ -d "$DEST/.git" ]; then
    echo "  • Updating $DEST"
    git -C "$DEST" fetch --quiet --depth 1 origin "$BRANCH"
    git -C "$DEST" reset --quiet --hard FETCH_HEAD
else
    echo "  • Downloading to $DEST"
    mkdir -p "$(dirname "$DEST")"
    git clone --quiet --depth 1 --branch "$BRANCH" "$REPO" "$DEST"
fi

# uv gives every distro the same tested Python (3.12) without needing python3-venv or sudo.
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
    echo "  • Installing uv (Python environment manager, to ~/.local/bin)"
    curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh >/dev/null
    command -v uv >/dev/null 2>&1 || die "Could not install uv. See https://docs.astral.sh/uv/ and run this installer again."
fi

missing=()
ldconfig -p 2>/dev/null | grep -q "libportaudio.so.2" || missing+=(libportaudio2)
ldconfig -p 2>/dev/null | grep -q "libxcb-cursor.so.0" || missing+=(libxcb-cursor0)

bash "$DEST/install.sh" --with-model "$@"

if [ "${#missing[@]}" -gt 0 ]; then
    echo
    say "One more step (needs your password once):"
    echo "    sudo apt install ${missing[*]}"
    echo "  libxcb-cursor0 lets the camera stay on top on GNOME; libportaudio2 powers the voice wave."
fi
