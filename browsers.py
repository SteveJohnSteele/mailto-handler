"""Finding browsers and building the command that opens a URL in one.

Standard library only.
"""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys

import config

# kind "chromium": supports --app=URL (a window without tabs or toolbar).
# kind "firefox": no app mode; --new-window is the closest.
KNOWN_BROWSERS = [
    {"id": "edge", "name": "Microsoft Edge", "kind": "chromium",
     "executables": ("microsoft-edge", "microsoft-edge-stable"),
     "flatpak": "com.microsoft.Edge"},
    {"id": "chrome", "name": "Google Chrome", "kind": "chromium",
     "executables": ("google-chrome", "google-chrome-stable"),
     "flatpak": "com.google.Chrome"},
    {"id": "chromium", "name": "Chromium", "kind": "chromium",
     "executables": ("chromium", "chromium-browser"),
     "flatpak": "org.chromium.Chromium"},
    {"id": "brave", "name": "Brave", "kind": "chromium",
     "executables": ("brave-browser", "brave", "brave-browser-stable"),
     "flatpak": "com.brave.Browser"},
    {"id": "vivaldi", "name": "Vivaldi", "kind": "chromium",
     "executables": ("vivaldi-stable", "vivaldi"),
     "flatpak": "com.vivaldi.Vivaldi"},
    {"id": "firefox", "name": "Firefox", "kind": "firefox",
     "executables": ("firefox",),
     "flatpak": "org.mozilla.firefox"},
]

SYSTEM_DEFAULT = {"id": "default", "name": "System default browser",
                  "kind": "default"}

_flatpak_ids = None


def _flatpak_apps():
    """Set of installed Flatpak application ids (cached)."""
    global _flatpak_ids
    if _flatpak_ids is None:
        _flatpak_ids = set()
        if shutil.which("flatpak"):
            try:
                out = subprocess.run(
                    ["flatpak", "list", "--app", "--columns=application"],
                    capture_output=True, text=True, timeout=10).stdout
                _flatpak_ids = {line.strip() for line in out.splitlines()
                                if line.strip()}
            except (OSError, subprocess.SubprocessError):
                pass
    return _flatpak_ids


def refresh():
    """Forget cached detection results (after installing a browser)."""
    global _flatpak_ids
    _flatpak_ids = None


def _command_for(browser):
    """The base command that starts a known browser, or None if missing."""
    for name in browser["executables"]:
        path = shutil.which(name)
        if path:
            return [path]
    if browser["flatpak"] in _flatpak_apps():
        return ["flatpak", "run", browser["flatpak"]]
    return None


def custom_browsers(cfg):
    result = []
    for item in cfg.get("custom_browsers", []):
        if isinstance(item, dict) and item.get("id") and item.get("command"):
            result.append({"id": item["id"],
                           "name": item.get("name") or item["id"],
                           "kind": "custom", "command": item["command"]})
    return result


def installed(cfg):
    """Browsers this machine can run: a list of (browser, base_command)."""
    found = []
    for browser in KNOWN_BROWSERS:
        command = _command_for(browser)
        if command:
            found.append((browser, command))
    for browser in custom_browsers(cfg):
        try:
            found.append((browser, shlex.split(browser["command"])))
        except ValueError:
            pass
    opener = shutil.which("xdg-open")
    if opener:
        found.append((SYSTEM_DEFAULT, [opener]))
    return found


def resolve(cfg):
    """Pick the browser to use: (browser, base_command) or (None, None)."""
    choices = installed(cfg)
    wanted = cfg.get("browser", "auto")
    if wanted != "auto":
        for browser, command in choices:
            if browser["id"] == wanted:
                return browser, command
        return None, None
    # Prefer a real browser over xdg-open when choosing automatically.
    for browser, command in choices:
        if browser["kind"] != "default":
            return browser, command
    return choices[0] if choices else (None, None)


def build_command(browser, base_command, url, app_window=True):
    """The full argv that opens `url`."""
    kind = browser["kind"]
    if kind == "chromium":
        command = list(base_command)
        command.append(("--app=" + url) if app_window else url)
        return command
    if kind == "firefox":
        command = list(base_command)
        if app_window:
            command.append("--new-window")
        command.append(url)
        return command
    if kind == "custom":
        parts = shlex.split(browser["command"])
        if any("{url}" in part for part in parts):
            return [part.replace("{url}", url) for part in parts]
        return parts + [url]
    return list(base_command) + [url]


EARLY_EXIT_SECONDS = 2


def launch(command):
    """Start the browser detached, logging its output.

    Returns an error message, or None on success.
    """
    try:
        os.makedirs(os.path.dirname(config.LOG_FILE), exist_ok=True)
        log = open(config.LOG_FILE, "w", encoding="utf-8")
        log.write("Command: %r\n\n" % (command,))
        log.flush()
    except OSError:
        log = subprocess.DEVNULL
    try:
        proc = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                stdout=log, stderr=subprocess.STDOUT,
                                start_new_session=True)
    except OSError as exc:
        return "Could not start %s: %s" % (command[0], exc)
    try:
        code = proc.wait(timeout=EARLY_EXIT_SECONDS)
    except subprocess.TimeoutExpired:
        return None  # still running: the browser started normally
    if code != 0:
        return ("The browser exited straight away (code %s). Details: %s"
                % (code, config.LOG_FILE))
    return None  # exit 0: handed the link to a browser that was already open


def open_url(cfg, url):
    """Open `url` using the configured browser. Returns an error or None."""
    browser, base = resolve(cfg)
    if browser is None:
        wanted = cfg.get("browser", "auto")
        if wanted == "auto":
            return "No web browser was found."
        return ("The browser '%s' chosen in settings is not installed."
                % wanted)
    command = build_command(browser, base, url,
                            app_window=cfg.get("app_window", True))
    return launch(command)


def show_error(message, title="Mailto handler"):
    """Show an error where the user will actually see it."""
    for cmd in (["kdialog", "--title", title, "--error", message],
                ["notify-send", "-u", "critical", title, message]):
        if shutil.which(cmd[0]):
            subprocess.run(cmd, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            return
    print("%s: %s" % (title, message), file=sys.stderr)