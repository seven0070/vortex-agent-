"""Desktop app entry point for Vortex Agent."""
from __future__ import annotations

import sys

from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from api_client import VortexApiClient
from backend_manager import BackendManager
from config import ConfigManager
from ui.main_window import MainWindow


def build_tray(app: QApplication, window: MainWindow) -> QSystemTrayIcon:
    tray = QSystemTrayIcon(QIcon(), parent=window)
    tray.setToolTip("Vortex Agent Desktop")

    menu = QMenu()
    show_action = QAction("Show", tray)
    hide_action = QAction("Hide", tray)
    quit_action = QAction("Quit", tray)

    show_action.triggered.connect(window.showNormal)
    hide_action.triggered.connect(window.hide)

    def quit_app() -> None:
        window._quit_to_tray = False
        window.backend_manager.stop()
        tray.hide()
        app.quit()

    quit_action.triggered.connect(quit_app)

    menu.addAction(show_action)
    menu.addAction(hide_action)
    menu.addSeparator()
    menu.addAction(quit_action)
    tray.setContextMenu(menu)
    tray.activated.connect(lambda *_: window.showNormal())
    tray.show()
    return tray


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Vortex Agent Desktop")

    config_manager = ConfigManager()
    config = config_manager.load()

    backend_manager = BackendManager(config)
    backend_manager.start_if_needed()

    api_client = VortexApiClient(config.active_backend_url)
    window = MainWindow(api_client, config, config_manager, backend_manager)
    window.show()
    _tray = build_tray(app, window)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
