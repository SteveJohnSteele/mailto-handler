"""Locations and persistent settings. Standard library only."""
from __future__ import annotations

import copy
import json
import os
import re
import tempfile

APP_ID = "mailto-handler"


def xdg_dir(variable, fallback):
    return os.environ.get(variable) or os.path.expanduser(fallback)


CONFIG_DIR = os.path.join(xdg_dir("XDG_CONFIG_HOME", "~/.config"), APP_ID)
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
# The browser's output from the most recent launch (overwritten each run).
LOG_FILE = os.path.join(xdg_dir("XDG_CACHE_HOME", "~/.cache"), APP_ID + ".log")

DEFAULTS = {
    "version": 1,
    "provider": "gmail",        # id of a built-in or custom provider
    "browser": "auto",          # "auto", a known browser id or a custom one
    "app_window": True,         # standalone window instead of a tab
    "custom_providers": [],     # [{"id", "name", "template"}]
    "custom_browsers": [],      # [{"id", "name", "command"}]
}


def load():
    """Return the settings, falling back to defaults for anything missing."""
    cfg = copy.deepcopy(DEFAULTS)
    try:
        with open(CONFIG_FILE, encoding="utf-8") as handle:
            stored = json.load(handle)
    except (OSError, ValueError):
        return cfg
    if isinstance(stored, dict):
        for key, default in DEFAULTS.items():
            if key in stored and isinstance(stored[key], type(default)):
                cfg[key] = stored[key]
    return cfg


def save(cfg):
    """Write the settings atomically. Raises OSError on failure."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=CONFIG_DIR, prefix=".config-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(cfg, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(tmp, CONFIG_FILE)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def new_id(prefix, name, taken):
    """Make an id like 'custom-my-mail' that is not in `taken`."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "item"
    base = "%s-%s" % (prefix, slug)
    candidate, number = base, 2
    while candidate in taken:
        candidate = "%s-%d" % (base, number)
        number += 1
    return candidate