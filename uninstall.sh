#!/bin/sh
# Remove Mailto Handler for the current user.
DEST="${XDG_DATA_HOME:-$HOME/.local/share}/mailto-handler"

pkill -f "$DEST/tray.py" 2>/dev/null || true
if [ -f "$DEST/system.py" ]; then
    python3 "$DEST/system.py" uninstall
fi
rm -rf "$DEST"
echo "Removed. Your settings are kept in ~/.config/mailto-handler (delete it if you like)."