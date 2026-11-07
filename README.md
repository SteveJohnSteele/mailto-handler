# Mailto Handler

Opens `mailto:` links in the webmail and browser you choose, from a system tray icon and a settings window. Built for KDE Plasma with PyQt6; nothing is ever sent, the webmail just opens a draft.

## Install

PyQt6 must be installed system-wide first (once):

| Distro | Command |
|---|---|
| Debian / Ubuntu | `sudo apt install python3-pyqt6` |
| Fedora | `sudo dnf install python3-pyqt6` |
| Arch / Manjaro | `sudo pacman -S python-pyqt6` |
| openSUSE | `sudo zypper install python3-qt6` |

Then, from this folder:

```sh
./install.sh
```

This copies the app to `~/.local/share/mailto-handler`, makes it your default mail app, adds it to your login items and opens the settings window. Run `./install.sh` again after changing the code to deploy the change. The folder you installed from can be moved or deleted afterwards.

To remove it: `./uninstall.sh`. Your settings stay in `~/.config/mailto-handler`.

For development you can also run `python3 tray.py --settings` straight from the folder; that copy is separate from the installed one.

## How it works

| File | Role |
|---|---|
| `handler.py` | What a clicked `mailto:` link runs. Standard library only, so links work even if the tray isn't running. |
| `providers.py` | `mailto:` parsing and the list of webmail services (URL templates). |
| `browsers.py` | Browser detection and the command that opens a URL. |
| `config.py` | Settings, stored in `~/.config/mailto-handler/config.json`. |
| `system.py` | Default-handler registration and autostart (`.desktop` files). |
| `tray.py`, `settings_window.py` | The tray icon, its menu, and the settings window. |

Left-click the tray icon for settings; right-click to switch service quickly.

## Services

Gmail, Outlook.com, Yahoo Mail, Fastmail and Proton Mail are built in. If your email is on a different website, such as one run by your employer or web host, **Add custom…** lets you enter that site's "new message" web address, with placeholders where the recipient, subject and so on go, for example `https://mail.example.com/compose?to={to}&subject={subject}`. Placeholders: `{to} {cc} {bcc} {subject} {body}`, and `{mailto}` for the whole link. Parameters whose placeholder is empty are left out.

These compose links are not officially documented, so the providers can change them at any time, and they have not been checked against live accounts:

- **Gmail**: uses Gmail's standard compose link.
- **Outlook.com**: `to`, `subject` and `body` are widely reported to work; Cc and Bcc are reported inconsistently.
- **Yahoo**: addresses only; prefilled fields can be lost if you were signed out.
- **Fastmail**: `to`, `cc`, `subject` and `body` are confirmed in a Fastmate bug report; `bcc` is assumed to work.
- **Proton**: passes the whole `mailto:` link in `#mailto=`, which is how Proton registers itself as a browser handler. Untested.

If one misbehaves, use the **Test** tab to see the exact address that is built, and fix it with a custom entry.

## Browsers

Edge, Chrome, Chromium, Brave and Vivaldi (native or Flatpak) open as a tab-less `--app=` window. Firefox has no app mode, so it gets a new window. "System default browser" (the default choice) uses `xdg-open`.

If a link does nothing, **System → Show last browser log** has the browser's output from the most recent launch.


## Licence

MIT. See the `LICENSE` file. You can use, change and share it freely.

## Credits

Created by Steve John Steele, with the help of [Claude](https://claude.ai), Anthropic's AI assistant, which wrote much of the code and documentation under the author's direction.

Gmail, Outlook, Yahoo Mail, Fastmail and Proton Mail are trademarks of their respective owners. This project is independent and is not affiliated with or endorsed by any of them. It only opens each service's own web page in your browser.