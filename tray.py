#!/usr/bin/env python3
"""System tray app for Mailto Handler. PyQt6.

    tray.py             start in the tray
    tray.py --settings  start (or ask the running tray) to show settings
"""
import os
import sys

from PyQt6.QtCore import QObject
from PyQt6.QtGui import QAction, QActionGroup
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

import browsers
import config
import providers
import system
from settings_window import SAMPLE_MAILTO, SettingsWindow, app_icon

SERVER_NAME = "mailto-handler-tray-%d" % os.getuid()


class Tray(QObject):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.window = SettingsWindow()
        self.window.saved.connect(self.refresh)
        self.tray = QSystemTrayIcon(app_icon())
        self.menu = QMenu()
        self.menu.aboutToShow.connect(self.build_menu)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self.on_activated)
        self.build_menu()
        self.refresh()
        self.tray.show()

    def refresh(self):
        provider = providers.find_provider(config.load())
        self.tray.setToolTip("Mailto Handler: %s" % provider["name"])
        self.build_menu()

    def build_menu(self):
        cfg = config.load()
        chosen = providers.find_provider(cfg)["id"]
        self.menu.clear()

        title = self.menu.addAction("Open mailto links in:")
        title.setEnabled(False)
        group = QActionGroup(self.menu)
        group.setExclusive(True)
        for provider in providers.all_providers(cfg):
            action = QAction(provider["name"], self.menu)
            action.setCheckable(True)
            action.setChecked(provider["id"] == chosen)
            action.triggered.connect(
                lambda _checked, pid=provider["id"]: self.choose(pid))
            group.addAction(action)
            self.menu.addAction(action)

        self.menu.addSeparator()
        self.menu.addAction("Settings…", self.show_settings)
        self.menu.addAction("Open a test email", self.test_compose)
        if not system.is_default():
            self.menu.addAction("Set as default mail app", self.make_default)
        self.menu.addSeparator()
        self.menu.addAction("Quit", self.app.quit)

    def choose(self, provider_id):
        cfg = config.load()
        cfg["provider"] = provider_id
        try:
            config.save(cfg)
        except OSError as exc:
            self.tray.showMessage("Mailto Handler",
                                  "Could not save: %s" % exc,
                                  QSystemTrayIcon.MessageIcon.Critical)
            return
        if self.window.isVisible():
            self.window.reload()
        self.refresh()

    def make_default(self):
        problem = system.install_handler()
        if problem:
            self.tray.showMessage("Mailto Handler", problem,
                                  QSystemTrayIcon.MessageIcon.Warning)
        else:
            self.tray.showMessage("Mailto Handler",
                                  "Now the default mail app.",
                                  QSystemTrayIcon.MessageIcon.Information)

    def test_compose(self):
        cfg = config.load()
        provider = providers.find_provider(cfg)
        problem = browsers.open_url(
            cfg, providers.build_url(provider, SAMPLE_MAILTO))
        if problem:
            self.tray.showMessage("Mailto Handler", problem,
                                  QSystemTrayIcon.MessageIcon.Critical)

    def on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_settings()

    def show_settings(self):
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()


def ask_running_instance():
    """Tell an already-running tray to show its settings. True if it did."""
    socket = QLocalSocket()
    socket.connectToServer(SERVER_NAME)
    if not socket.waitForConnected(500):
        return False
    socket.write(b"settings")
    socket.flush()
    socket.waitForBytesWritten(500)
    socket.disconnectFromServer()
    return True


def main():
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Mailto Handler")
    app.setDesktopFileName("mailto-handler-settings")
    app.setQuitOnLastWindowClosed(False)
    want_settings = "--settings" in sys.argv[1:]

    if ask_running_instance():
        return 0

    tray = Tray(app)
    server = QLocalServer()
    QLocalServer.removeServer(SERVER_NAME)
    server.listen(SERVER_NAME)

    def on_connection():
        client = server.nextPendingConnection()
        if client is not None:
            client.readyRead.connect(tray.show_settings)
            client.disconnected.connect(client.deleteLater)

    server.newConnection.connect(on_connection)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        want_settings = True  # nowhere to put an icon: show the window
    if want_settings:
        tray.show_settings()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
