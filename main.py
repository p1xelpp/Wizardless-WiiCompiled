import os
from pathlib import Path
import subprocess
import sys

import pycurl
from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parent
INSTALLER = ROOT / "WiiCompiled-Setup.exe"
ISO = ROOT / "MarioKart.iso"
OUTPUT_DIR = ROOT / "WiiCompiled"

def get_wii_compiled_installer(log):
    log("Downloading WiiCompiled-Setup.exe...")
    url = "https://github.com/patchzyy/Wiicompiled/releases/download/v0.2.32/WiiCompiled-Setup.exe"
    with INSTALLER.open("wb") as installer_file:
        curl = pycurl.Curl()
        try:
            curl.setopt(pycurl.URL, url)
            curl.setopt(pycurl.WRITEDATA, installer_file)
            curl.perform()
        finally:
            curl.close()
    log("Download complete.")

def run_wii_compiled(log):
    if not ISO.is_file():
        raise FileNotFoundError(
            "MarioKart.iso was not found. Place it beside this script and try again."
        )

    if not INSTALLER.is_file():
        get_wii_compiled_installer(log)
    else:
        log("WiiCompiled-Setup.exe already exists. Skipping download.")

    command = [
        str(INSTALLER),
        "--silent",
        "--game",
        str(ISO),
        "--install-dir",
        str(OUTPUT_DIR),
        "--portable",
    ]
    log("Starting WiiCompiled build...")
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    for line in process.stdout:
        log(line.rstrip())
    return_code = process.wait()
    if return_code:
        raise subprocess.CalledProcessError(return_code, command)
    log("Build completed successfully.")

def make_desktop_shortcut(log):
    target = OUTPUT_DIR / "Base" / "WiiCompiled.exe"
    if not target.is_file():
        raise FileNotFoundError(f"Built executable was not found: {target}")
    if os.name != "nt":
        raise OSError("Desktop shortcuts are only supported on Windows.")

    user_profile = Path(os.environ.get("USERPROFILE", Path.home()))
    desktop_candidates = [user_profile / "Desktop"]
    one_drive = os.environ.get("OneDrive")
    if one_drive:
        desktop_candidates.append(Path(one_drive) / "Desktop")
    desktop_candidates.append(user_profile / "OneDrive" / "Desktop")

    shortcut_contents = (
        "[InternetShortcut]\n"
        f"URL=file:///{target.as_posix()}\n"
        f"WorkingDirectory={target.parent}\n"
        f"IconFile={target}\n"
        "IconIndex=0\n"
    )
    created_paths = set()
    for desktop in desktop_candidates:
        desktop = desktop.resolve()
        if desktop in created_paths:
            continue
        if desktop.name == "Desktop" and not desktop.exists():
            if desktop.parent.name == "OneDrive":
                log(f"OneDrive Desktop not found, skipping: {desktop}")
                continue
            desktop.mkdir(parents=True, exist_ok=True)
        shortcut = desktop / "WiiCompiled.url"
        shortcut.write_text(shortcut_contents, encoding="utf-8")
        created_paths.add(desktop)
        log(f"Desktop shortcut created: {shortcut}")

class BuildWorker(QObject):
    log_message = Signal(str)
    finished = Signal(bool)

    def __init__(self, create_shortcut):
        super().__init__()
        self.create_shortcut = create_shortcut

    @Slot()
    def run(self):
        try:
            run_wii_compiled(self.log_message.emit)
            if self.create_shortcut:
                make_desktop_shortcut(self.log_message.emit)
            self.finished.emit(True)
        except Exception as error:
            self.log_message.emit(f"ERROR: {error}")
            self.finished.emit(False)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WiiCompiled Builder")
        self.resize(760, 520)
        self.thread = None
        self.worker = None

        self.build_button = QPushButton("Build")
        self.build_button.clicked.connect(self.start_build)
        self.shortcut_checkbox = QCheckBox("Create desktop shortcut")
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("Build output will appear here...")

        layout = QVBoxLayout()
        layout.addWidget(self.shortcut_checkbox)
        layout.addWidget(self.build_button)
        layout.addWidget(self.log_view, 1)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    @Slot()
    def start_build(self):
        self.build_button.setEnabled(False)
        self.shortcut_checkbox.setEnabled(False)
        self.log_view.clear()
        self.log_view.appendPlainText("Preparing build...")

        self.thread = QThread(self)
        self.worker = BuildWorker(self.shortcut_checkbox.isChecked())
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.log_message.connect(self.log_view.appendPlainText)
        self.worker.finished.connect(self.build_finished)
        self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    @Slot(bool)
    def build_finished(self, success):
        self.build_button.setEnabled(True)
        self.shortcut_checkbox.setEnabled(True)
        self.log_view.appendPlainText(
            "Ready." if success else "Build failed. See the log above."
        )

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(
        """
        QWidget { background: #202124; color: #f1f3f4; }
        QPushButton { background: #3b82f6; border: 0; border-radius: 5px; padding: 9px; }
        QPushButton:hover { background: #60a5fa; }
        QPushButton:disabled { background: #4b5563; color: #9ca3af; }
        QCheckBox { spacing: 8px; padding: 5px 0; }
        QPlainTextEdit { background: #111315; border: 1px solid #3c4043; border-radius: 5px; }
        """
    )
    window = MainWindow()
    window.show()
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
