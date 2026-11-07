"""Desktop integration: default mailto handler and autostart (XDG).

Standard library only. Run `python3 system.py install` to register the
handler without the GUI, or `python3 system.py uninstall` to undo it.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

import config

HERE = os.path.dirname(os.path.abspath(__file__))
MIME = "x-scheme-handler/mailto"

APPLICATIONS_DIR = os.path.join(
    config.xdg_dir("XDG_DATA_HOME", "~/.local/share"), "applications")
AUTOSTART_DIR = os.path.join(
    config.xdg_dir("XDG_CONFIG_HOME", "~/.config"), "autostart")

HANDLER_DESKTOP = "mailto-handler.desktop"
SETTINGS_DESKTOP = "mailto-handler-settings.desktop"
AUTOSTART_DESKTOP = "mailto-handler-tray.desktop"


FIELD_CODES = ("%u", "%U", "%f", "%F")


def exec_quote(arg):
    """Quote one argument for the Exec= line of a .desktop file."""
    if arg in FIELD_CODES:  # %u etc. must reach the desktop environment as-is
        return arg
    if not arg or any(c in arg for c in ' \t\n"\'\\><~|&;$*?#()`%'):
        escaped = (arg.replace("\\", "\\\\").replace('"', '\\"')
                   .replace("`", "\\`").replace("$", "\\$")
                   .replace("%", "%%"))
        return '"%s"' % escaped
    return arg


def _exec(script, *extra):
    parts = [sys.executable, os.path.join(HERE, script)] + list(extra)
    return " ".join(exec_quote(p) for p in parts)


def _write(directory, name, text):
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


def _refresh_desktop_database():
    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", APPLICATIONS_DIR],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def handler_desktop_text():
    return ("[Desktop Entry]\n"
            "Type=Application\n"
            "Name=Mailto Handler\n"
            "Comment=Open mailto: links in your webmail\n"
            "Exec=%s\n"
            "Icon=mail-message-new\n"
            "Terminal=false\n"
            "NoDisplay=true\n"
            "MimeType=%s;\n" % (_exec("handler.py", "%u"), MIME))


def settings_desktop_text():
    return ("[Desktop Entry]\n"
            "Type=Application\n"
            "Name=Mailto Handler Settings\n"
            "Comment=Choose which webmail and browser mailto: links open in\n"
            "Exec=%s\n"
            "Icon=mail-message-new\n"
            "Terminal=false\n"
            "Categories=Network;Email;Settings;\n" % _exec("tray.py", "--settings"))


def autostart_desktop_text():
    return ("[Desktop Entry]\n"
            "Type=Application\n"
            "Name=Mailto Handler\n"
            "Exec=%s\n"
            "Icon=mail-message-new\n"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n" % _exec("tray.py"))


def install_handler():
    """Create the launcher entries and make this the default mailto handler.

    Returns an error message or None.
    """
    try:
        _write(APPLICATIONS_DIR, HANDLER_DESKTOP, handler_desktop_text())
        _write(APPLICATIONS_DIR, SETTINGS_DESKTOP, settings_desktop_text())
    except OSError as exc:
        return "Could not write the .desktop files: %s" % exc
    _refresh_desktop_database()
    if not shutil.which("xdg-mime"):
        return "xdg-mime was not found; set the default mail app manually."
    result = subprocess.run(["xdg-mime", "default", HANDLER_DESKTOP, MIME],
                            capture_output=True, text=True)
    if result.returncode != 0:
        return "xdg-mime failed: %s" % (result.stderr.strip() or result.returncode)
    return None


def uninstall_handler():
    """Remove our launcher entries. Returns an error message or None."""
    problem = None
    for directory, name in ((APPLICATIONS_DIR, HANDLER_DESKTOP),
                            (APPLICATIONS_DIR, SETTINGS_DESKTOP),
                            (AUTOSTART_DIR, AUTOSTART_DESKTOP)):
        try:
            os.unlink(os.path.join(directory, name))
        except FileNotFoundError:
            pass
        except OSError as exc:
            problem = "Could not remove %s: %s" % (name, exc)
    _refresh_desktop_database()
    return problem


def default_handler():
    """The .desktop id currently set as the mailto handler, or ''."""
    if not shutil.which("xdg-mime"):
        return ""
    result = subprocess.run(["xdg-mime", "query", "default", MIME],
                            capture_output=True, text=True)
    return result.stdout.strip()


def is_default():
    return default_handler() == HANDLER_DESKTOP


def is_autostart():
    return os.path.exists(os.path.join(AUTOSTART_DIR, AUTOSTART_DESKTOP))


def set_autostart(enabled):
    """Turn start-at-login on or off. Returns an error message or None."""
    try:
        if enabled:
            _write(AUTOSTART_DIR, AUTOSTART_DESKTOP, autostart_desktop_text())
        else:
            try:
                os.unlink(os.path.join(AUTOSTART_DIR, AUTOSTART_DESKTOP))
            except FileNotFoundError:
                pass
    except OSError as exc:
        return "Could not change autostart: %s" % exc
    return None


def main(argv):
    action = argv[0] if argv else ""
    if action == "install":
        problem = install_handler()
        problem = set_autostart(True) or problem
    elif action == "uninstall":
        problem = uninstall_handler()
    else:
        print("usage: system.py install|uninstall", file=sys.stderr)
        return 2
    if problem:
        print(problem, file=sys.stderr)
        return 1
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))