#!/bin/sh
# Install Mailto Handler for the current user (no root needed).
#
#   ./install.sh             install or update, then open the settings window
#   ./install.sh --no-start  install or update without starting the tray
#
# Uses your system Python and the system-wide PyQt6.
# Run it again after changing the code to deploy your changes.
set -e

SRC=$(cd "$(dirname "$0")" && pwd)
DEST="${XDG_DATA_HOME:-$HOME/.local/share}/mailto-handler"

command -v python3 >/dev/null 2>&1 || { echo "python3 is required." >&2; exit 1; }

if ! python3 -c "import PyQt6.QtWidgets" >/dev/null 2>&1; then
    cat >&2 <<'EOF'
PyQt6 is not installed for python3. Install it system-wide first:
  Debian/Ubuntu:  sudo apt install python3-pyqt6
  Fedora:         sudo dnf install python3-pyqt6
  Arch/Manjaro:   sudo pacman -S python-pyqt6
  openSUSE:       sudo zypper install python3-qt6
Then run ./install.sh again.
EOF
    exit 1
fi

echo "Installing to $DEST"
pkill -f "$DEST/tray.py" 2>/dev/null || true   # stop an older running copy
mkdir -p "$DEST"
cp "$SRC"/*.py "$DEST"/

# Registers the mailto: handler, adds the launcher entries, starts at login.
python3 "$DEST/system.py" install

if [ "$1" != "--no-start" ]; then
    nohup python3 "$DEST/tray.py" --settings >/dev/null 2>&1 &
fi
echo "Done. Mailto Handler is installed."