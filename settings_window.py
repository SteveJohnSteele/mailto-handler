"""The settings window. PyQt6."""
from __future__ import annotations

import copy
import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF
from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QTabWidget, QVBoxLayout, QWidget)

import browsers
import config
import providers
import system

SAMPLE_MAILTO = ("mailto:alice@example.com?cc=bob@example.com"
                 "&bcc=carol@example.com"
                 "&subject=Hello%20there&body=Line%20one%0ALine%20two")


def app_icon():
    """The theme's mail icon, or a drawn envelope if the theme lacks one."""
    theme = QIcon.fromTheme("mail-message-new")
    if not theme.isNull():
        return theme
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#3b82f6"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(QRectF(4, 12, 56, 40), 6, 6)
    painter.setPen(QPen(QColor("white"), 3, Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPolyline(QPolygonF([QPointF(10, 20), QPointF(32, 38),
                                    QPointF(54, 20)]))
    painter.end()
    return QIcon(pixmap)


def heading(text):
    label = QLabel(text)
    font = label.font()
    font.setBold(True)
    font.setPointSizeF(font.pointSizeF() * 1.25)
    label.setFont(font)
    return label


def hint(text):
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet("color: palette(placeholder-text);")
    return label


class ProviderDialog(QDialog):
    """Add or edit a custom webmail provider."""

    def __init__(self, parent, name="", template=""):
        super().__init__(parent)
        self.setWindowTitle("Custom email service")
        self.setMinimumWidth(520)
        self.name_edit = QLineEdit(name)
        self.name_edit.setPlaceholderText("e.g. Work webmail")
        self.template_edit = QLineEdit(template)
        self.template_edit.setPlaceholderText(
            "https://mail.example.com/compose?to={to}&subject={subject}")
        self.problem = QLabel()
        self.problem.setStyleSheet("color: #c0392b;")
        self.problem.setWordWrap(True)
        self.preview = QLineEdit()
        self.preview.setReadOnly(True)

        form = QFormLayout()
        form.addRow("Name:", self.name_edit)
        form.addRow("Compose address:", self.template_edit)
        form.addRow("Preview:", self.preview)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.problem)
        layout.addWidget(hint(
            "Placeholders: {to} {cc} {bcc} {subject} {body}, or {mailto} for "
            "the whole mailto: link. Parameters whose placeholders are empty "
            "are left out. Values are URL-encoded for you."))
        layout.addWidget(self.buttons)
        self.name_edit.textChanged.connect(self.validate)
        self.template_edit.textChanged.connect(self.validate)
        self.validate()

    def validate(self):
        template = self.template_edit.text().strip()
        problem = providers.template_problem(template) if template else \
            "Enter the compose address."
        if not problem and not self.name_edit.text().strip():
            problem = "Enter a name."
        self.problem.setText(problem or "")
        ok = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setEnabled(problem is None)
        self.preview.setText(
            providers.fill_template(template, providers.parse_mailto(
                SAMPLE_MAILTO), SAMPLE_MAILTO) if problem is None else "")

    def values(self):
        return self.name_edit.text().strip(), self.template_edit.text().strip()


class SettingsWindow(QMainWindow):
    saved = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mailto Handler Settings")
        self.setWindowIcon(app_icon())
        self.resize(700, 520)
        self.stored = config.load()
        self.cfg = copy.deepcopy(self.stored)
        self._loading = False

        self.tabs = QTabWidget()
        for title, builder in (("Email service", self.build_service_page),
                               ("Browser", self.build_browser_page),
                               ("Test", self.build_test_page),
                               ("System", self.build_system_page)):
            self.tabs.addTab(builder(), title)

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save)
        self.revert_button = QPushButton("Revert")
        self.revert_button.clicked.connect(self.reload)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        self.status = QLabel()
        self.status.setStyleSheet("color: palette(placeholder-text);")

        bottom = QHBoxLayout()
        bottom.addWidget(self.status, 1)
        bottom.addWidget(self.revert_button)
        bottom.addWidget(self.save_button)
        bottom.addWidget(close_button)

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.addWidget(self.tabs, 1)
        layout.addLayout(bottom)
        self.setCentralWidget(root)

        self.reload()
        self.tabs.setCurrentIndex(0)

    # ------------------------------------------------------------ pages
    def build_service_page(self):
        page = QWidget()
        self.provider_combo = QComboBox()
        self.provider_combo.currentIndexChanged.connect(self.provider_selected)
        self.add_provider_button = QPushButton("Add custom…")
        self.edit_provider_button = QPushButton("Edit…")
        self.remove_provider_button = QPushButton("Remove")
        self.add_provider_button.clicked.connect(self.add_provider)
        self.edit_provider_button.clicked.connect(self.edit_provider)
        self.remove_provider_button.clicked.connect(self.remove_provider)
        self.provider_fields = QLabel()
        self.provider_fields.setTextFormat(Qt.TextFormat.RichText)
        self.provider_note = hint("")
        self.provider_template = QPlainTextEdit()
        self.provider_template.setReadOnly(True)
        self.provider_template.setMaximumHeight(70)
        self.provider_preview = QPlainTextEdit()
        self.provider_preview.setReadOnly(True)
        self.provider_preview.setMaximumHeight(90)

        top = QHBoxLayout()
        top.addWidget(QLabel("Open mailto links in:"))
        top.addWidget(self.provider_combo, 1)
        for button in (self.add_provider_button, self.edit_provider_button,
                       self.remove_provider_button):
            top.addWidget(button)

        layout = QVBoxLayout(page)
        layout.addLayout(top)
        layout.addWidget(self.provider_fields)
        layout.addWidget(self.provider_note)
        layout.addWidget(QLabel("Compose address template:"))
        layout.addWidget(self.provider_template)
        layout.addWidget(QLabel("Example (from a sample mailto: link):"))
        layout.addWidget(self.provider_preview)
        layout.addStretch(1)
        return page

    def build_browser_page(self):
        page = QWidget()
        self.browser_combo = QComboBox()
        self.browser_combo.currentIndexChanged.connect(self.browser_changed)
        self.app_window_check = QCheckBox(
            "Open in a standalone window (no tabs or address bar)")
        self.app_window_check.toggled.connect(self.app_window_changed)
        self.app_window_hint = QLabel()
        self.app_window_hint.setStyleSheet("color: palette(placeholder-text);")
        self.browser_missing = QLabel()
        self.browser_missing.setStyleSheet("color: #c0392b;")
        self.browser_missing.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Browser:", self.browser_combo)
        form.addRow("", self.app_window_check)
        form.addRow("", self.app_window_hint)

        layout = QVBoxLayout(page)
        layout.addLayout(form)
        layout.addWidget(self.browser_missing)
        layout.addStretch(1)
        return page

    def build_test_page(self):
        page = QWidget()
        self.test_input = QLineEdit(SAMPLE_MAILTO)
        self.test_input.textChanged.connect(self.update_test_preview)
        self.test_output = QPlainTextEdit()
        self.test_output.setReadOnly(True)
        self.test_output.setFixedHeight(
            self.test_output.fontMetrics().lineSpacing() * 4 + 16)
        self.test_problem = QLabel()
        self.test_problem.setStyleSheet("color: #c0392b;")
        self.test_problem.setWordWrap(True)
        self.test_open = QPushButton("Test")
        self.test_open.clicked.connect(self.run_test)

        buttons = QHBoxLayout()
        buttons.addWidget(self.test_open)
        buttons.addStretch(1)

        layout = QVBoxLayout(page)
        layout.addWidget(hint("Try the current (even unsaved) settings. "
                              "Nothing is sent; the webmail only opens a "
                              "draft."))
        layout.addWidget(QLabel("mailto: link:"))
        layout.addWidget(self.test_input)
        layout.addWidget(QLabel("Resulting address:"))
        layout.addWidget(self.test_output)
        layout.addWidget(self.test_problem)
        layout.addLayout(buttons)
        layout.addStretch(1)
        return page

    def build_system_page(self):
        page = QWidget()
        self.default_label = QLabel()
        self.default_label.setWordWrap(True)
        self.default_button = QPushButton("Set as default mail app")
        self.default_button.clicked.connect(self.make_default)
        self.autostart_check = QCheckBox("Start the tray icon when I log in")
        self.autostart_check.toggled.connect(self.autostart_toggled)
        log_button = QPushButton("Show last browser log")
        log_button.clicked.connect(self.show_log)
        paths = QLabel("Settings file: %s" % config.CONFIG_FILE)
        paths.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        paths.setWordWrap(True)

        box = QGroupBox("Default mail app")
        box_layout = QVBoxLayout(box)
        box_layout.addWidget(self.default_label)
        row = QHBoxLayout()
        row.addWidget(self.default_button)
        row.addStretch(1)
        box_layout.addLayout(row)
        box_layout.addWidget(hint(
            "This registers Mailto Handler for mailto: links. On KDE you can "
            "also check System Settings → Applications → Default Applications "
            "→ Email client."))

        layout = QVBoxLayout(page)
        layout.addWidget(box)
        layout.addWidget(self.autostart_check)
        row = QHBoxLayout()
        row.addWidget(log_button)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addWidget(paths)
        layout.addStretch(1)
        return page

    # ------------------------------------------------- loading and state
    def reload(self):
        """Discard unsaved edits and show what is stored."""
        self.stored = config.load()
        self.cfg = copy.deepcopy(self.stored)
        self.refresh_all()

    def refresh_all(self):
        self._loading = True
        try:
            self.fill_providers()
            self.fill_browsers()
            self.app_window_check.setChecked(self.cfg["app_window"])
            self.refresh_system()
        finally:
            self._loading = False
        self.update_browser_controls()
        self.update_test_preview()
        self.update_dirty()

    def update_dirty(self):
        dirty = self.cfg != self.stored
        self.save_button.setEnabled(dirty)
        self.revert_button.setEnabled(dirty)
        self.status.setText("Unsaved changes" if dirty else "")

    def save(self):
        try:
            config.save(self.cfg)
        except OSError as exc:
            QMessageBox.critical(self, "Could not save",
                                 "The settings could not be written:\n%s" % exc)
            return False
        self.stored = copy.deepcopy(self.cfg)
        self.update_dirty()
        self.status.setText("Saved")
        self.saved.emit()
        return True

    def closeEvent(self, event):
        if self.cfg != self.stored:
            answer = QMessageBox.question(
                self, "Unsaved changes", "Save your changes before closing?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel)
            if answer == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if answer == QMessageBox.StandardButton.Save and not self.save():
                event.ignore()
                return
            if answer == QMessageBox.StandardButton.Discard:
                self.reload()
        event.accept()

    # ------------------------------------------------- email service page
    def fill_providers(self):
        chosen = providers.find_provider(self.cfg)["id"]
        self.provider_combo.blockSignals(True)
        self.provider_combo.clear()
        for provider in providers.all_providers(self.cfg):
            self.provider_combo.addItem(provider["name"], provider["id"])
        self.provider_combo.setCurrentIndex(
            max(self.provider_combo.findData(chosen), 0))
        self.provider_combo.blockSignals(False)
        self.provider_selected()

    def current_provider(self):
        provider_id = self.provider_combo.currentData()
        if provider_id is None:
            return None
        return providers.find_provider(self.cfg, provider_id)

    def provider_selected(self, _index=None):
        provider = self.current_provider()
        if provider is None:
            return
        supported = providers.supported_fields(provider["template"])
        self.provider_fields.setText("&nbsp;&nbsp;&nbsp;".join(
            "%s <span style='color:%s'>%s</span>" % (
                label, "#2e9e4f" if key in supported else "#c0392b",
                "&#10003;" if key in supported else "&#10007;")
            for key, label in providers.FIELD_LABELS))
        self.provider_note.setText(provider["note"])
        self.provider_note.setVisible(bool(provider["note"]))
        self.provider_template.setPlainText(provider["template"])
        self.provider_preview.setPlainText(
            providers.build_url(provider, SAMPLE_MAILTO))
        custom = not provider["builtin"]
        self.edit_provider_button.setEnabled(custom)
        self.remove_provider_button.setEnabled(custom)
        if not self._loading:
            self.cfg["provider"] = provider["id"]
            self.update_test_preview()
            self.update_dirty()

    def add_provider(self):
        dialog = ProviderDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name, template = dialog.values()
        taken = {p["id"] for p in providers.all_providers(self.cfg)}
        new_id = config.new_id("custom", name, taken)
        self.cfg["custom_providers"].append(
            {"id": new_id, "name": name, "template": template})
        self.cfg["provider"] = new_id
        self.refresh_all()

    def edit_provider(self):
        provider = self.current_provider()
        if provider is None or provider["builtin"]:
            return
        dialog = ProviderDialog(self, provider["name"], provider["template"])
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name, template = dialog.values()
        for item in self.cfg["custom_providers"]:
            if item["id"] == provider["id"]:
                item["name"], item["template"] = name, template
        self.refresh_all()

    def remove_provider(self):
        provider = self.current_provider()
        if provider is None or provider["builtin"]:
            return
        self.cfg["custom_providers"] = [
            p for p in self.cfg["custom_providers"] if p["id"] != provider["id"]]
        if self.cfg["provider"] == provider["id"]:
            self.cfg["provider"] = providers.DEFAULT_PROVIDER
        self.refresh_all()

    # ------------------------------------------------------ browser page
    def fill_browsers(self):
        self.browser_combo.blockSignals(True)
        self.browser_combo.clear()
        known = set()
        for browser, _command in browsers.installed(self.cfg):
            self.browser_combo.addItem(browser["name"], browser["id"])
            known.add(browser["id"])
        wanted = self.cfg["browser"]
        if wanted not in known:
            self.browser_combo.addItem("%s (not installed)" % wanted, wanted)
        index = self.browser_combo.findData(wanted)
        self.browser_combo.setCurrentIndex(max(index, 0))
        self.browser_combo.blockSignals(False)

    def selected_browser(self):
        """The browser dict that the combo currently stands for, or None."""
        wanted = self.browser_combo.currentData()
        for browser, _command in browsers.installed(self.cfg):
            if browser["id"] == wanted:
                return browser
        return None

    def update_browser_controls(self):
        browser = self.selected_browser()
        kind = browser["kind"] if browser else ""
        self.app_window_check.setEnabled(kind in ("chromium", "firefox"))
        if kind == "chromium":
            text = "Supported by this browser."
        elif kind == "firefox":
            text = "Firefox can't hide its tabs; it opens a normal window."
        elif kind == "default":
            text = "Not available with the system default browser."
        else:
            text = ""
        self.app_window_hint.setText(text)
        self.browser_missing.setText(
            "The browser you chose is not installed, so mailto links will "
            "show an error until you pick another."
            if browser is None else "")

    def browser_changed(self, _index):
        if self._loading:
            return
        self.cfg["browser"] = self.browser_combo.currentData()
        self.update_browser_controls()
        self.update_dirty()

    def app_window_changed(self, checked):
        if not self._loading:
            self.cfg["app_window"] = checked
            self.update_dirty()

    # --------------------------------------------------------- test page
    def update_test_preview(self, *_args):
        provider = providers.find_provider(self.cfg)
        try:
            url = providers.build_url(provider, self.test_input.text().strip())
        except ValueError:
            self.test_output.setPlainText("")
            self.test_problem.setText("That is not a mailto: link.")
            self.test_open.setEnabled(False)
            return
        self.test_output.setPlainText(url)
        self.test_problem.setText("")
        self.test_open.setEnabled(True)

    def run_test(self):
        problem = browsers.open_url(self.cfg, self.test_output.toPlainText())
        self.test_problem.setText(problem or "")

    # ------------------------------------------------------- system page
    def refresh_system(self):
        current = system.default_handler()
        if current == system.HANDLER_DESKTOP:
            text = "Mailto Handler is the default mail app."
            self.default_button.setText("Re-register")
        elif current:
            text = "The default mail app is currently: %s" % current
            self.default_button.setText("Set as default mail app")
        else:
            text = "No default mail app is set."
            self.default_button.setText("Set as default mail app")
        self.default_label.setText(text)
        self.autostart_check.blockSignals(True)
        self.autostart_check.setChecked(system.is_autostart())
        self.autostart_check.blockSignals(False)

    def make_default(self):
        problem = system.install_handler()
        if problem:
            QMessageBox.warning(self, "Could not register", problem)
        self.refresh_system()

    def autostart_toggled(self, checked):
        problem = system.set_autostart(checked)
        if problem:
            QMessageBox.warning(self, "Autostart", problem)
        self.refresh_system()

    def show_log(self):
        try:
            with open(config.LOG_FILE, encoding="utf-8") as handle:
                text = handle.read()
        except OSError:
            text = "No log yet (%s)." % config.LOG_FILE
        dialog = QDialog(self)
        dialog.setWindowTitle("Last browser log")
        dialog.resize(640, 360)
        view = QPlainTextEdit(text)
        view.setReadOnly(True)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(dialog.reject)
        close.accepted.connect(dialog.accept)
        layout = QVBoxLayout(dialog)
        layout.addWidget(view)
        layout.addWidget(close)
        close.button(QDialogButtonBox.StandardButton.Close).clicked.connect(
            dialog.accept)
        dialog.exec()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_system()