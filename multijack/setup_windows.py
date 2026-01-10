import json
import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import state
from .config import set_config_option
from .localization import get_string, load_localization
from .main_window import MJMainWindow
from .paths import (
    get_default_config_location,
    get_default_steam_location,
    get_default_steamapps_location,
)


def _load_config():
    with open(
        os.path.join(get_default_config_location(), "config.json"),
        "r",
        encoding="utf-8",
    ) as config_file:
        return json.load(config_file)


def _show_window(owner, attr_name, window_cls):
    window = window_cls()
    setattr(owner, attr_name, window)
    window.show()


def _make_centered_label(text, parent):
    label = QLabel(text, parent)
    font = label.font()
    font.setPointSize(11)
    label.setFont(font)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label


class mj_language_selection_window(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("MultiJack")
        self.setGeometry(100, 100, 400, 300)

        widget = QWidget(self)
        self.setCentralWidget(widget)

        layout = QVBoxLayout(widget)

        welcome_label = _make_centered_label(
            "Welcome to MultiJack!\nPlease select your language.",
            self,
        )

        self.languageList = QListWidget(self)
        self.localization_data = load_localization()
        for code, name in self.localization_data.get("language_names", {}).items():
            self.languageList.addItem(name)

        continue_button = QPushButton("Continue", self)
        continue_button.clicked.connect(self.on_continue_clicked)

        layout.addWidget(welcome_label)
        layout.addWidget(self.languageList)
        layout.addWidget(continue_button)

    def on_continue_clicked(self):
        selected_language_option = self.languageList.currentItem()

        if selected_language_option is None:
            QMessageBox.warning(self, "MultiJack", "Please select a language.")
            return

        selected_language_text = selected_language_option.text()

        language_code = None
        for code, name in self.localization_data.get("language_names", {}).items():
            if name == selected_language_text:
                language_code = code
                break

        if language_code:
            state.selected_language = language_code
            set_config_option({"language": language_code})
            self.close()
            self.config_data = _load_config()
            if self.config_data.get("steam_location") == "":
                _show_window(
                    self,
                    "open_mj_steam_location_config_window",
                    mj_steam_location_config_window,
                )
            elif self.config_data.get("install_location") == "":
                _show_window(
                    self,
                    "open_mj_install_location_config_window",
                    mj_install_location_config_window,
                )
            else:
                _show_window(self, "open_main_window", MJMainWindow)

        else:
            QMessageBox.critical(self, "MultiJack", "Language selection failed.")


class mj_steam_location_config_window(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("MultiJack")
        self.setGeometry(100, 100, 400, 100)

        widget = QWidget(self)
        self.setCentralWidget(widget)

        layout = QVBoxLayout(widget)

        set_location_label = _make_centered_label(
            get_string("select_steam_location"), self
        )

        self.set_location_lineedit = QLineEdit(self)
        self.set_location_lineedit.setText(get_default_steam_location())

        browseButton = QPushButton(get_string("browse"), self)
        browseButton.clicked.connect(self.browse)

        continue_button = QPushButton(get_string("continue"), self)
        continue_button.clicked.connect(self.set_steam_location)

        layout.addWidget(set_location_label)
        layout.addWidget(self.set_location_lineedit)
        layout.addWidget(browseButton)
        layout.addWidget(continue_button)

    def set_steam_location(self):
        set_config_option({"steam_location": self.set_location_lineedit.text()})
        self.close()
        config_data = _load_config()
        if config_data.get("language") == "":
            _show_window(
                self, "open_language_selection_window", mj_language_selection_window
            )
        elif config_data.get("install_location") == "":
            _show_window(
                self,
                "open_install_location_config_window",
                mj_install_location_config_window,
            )
        elif config_data.get("env_location") == "":
            _show_window(
                self, "open_env_location_config_window", mj_env_location_config_window
            )
        else:
            _show_window(self, "open_main_window", MJMainWindow)

    def browse(self):
        folder_path = QFileDialog.getExistingDirectory(
            self, get_string("select_steam_location")
        )
        if folder_path:
            if not self.validate_folder(
                os.path.join(folder_path, "steamapps", "common")
            ):
                QMessageBox.warning(
                    self, "MultiJack", get_string("no_steamapps_installs_error")
                )
                _show_window(
                    self,
                    "open_mj_install_location_config_window",
                    mj_install_location_config_window,
                )
            else:
                self.set_location_lineedit.setText(folder_path)

    def validate_folder(self, folder_path):
        root_dirs = [
            entry
            for entry in os.listdir(folder_path)
            if os.path.isdir(os.path.join(folder_path, entry))
        ]

        for dir_name in root_dirs:
            if any(
                dir_name.startswith(prefix)
                for prefix in ["The Jackbox", "Quiplash", "Fibbage", "Drawful"]
            ):
                return True
        return False


class mj_install_location_config_window(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("MultiJack")
        self.setGeometry(100, 100, 400, 100)

        widget = QWidget(self)
        self.setCentralWidget(widget)

        layout = QVBoxLayout(widget)

        set_location_label = _make_centered_label(
            get_string("select_install_location"), self
        )

        self.set_location_lineedit = QLineEdit(self)
        self.set_location_lineedit.setText(get_default_steamapps_location())

        browseButton = QPushButton(get_string("browse"), self)
        browseButton.clicked.connect(self.browse)

        continue_button = QPushButton(get_string("continue"), self)
        continue_button.clicked.connect(self.setinstall_location)

        layout.addWidget(set_location_label)
        layout.addWidget(self.set_location_lineedit)
        layout.addWidget(browseButton)
        layout.addWidget(continue_button)

    def setinstall_location(self):
        set_config_option({"install_location": self.set_location_lineedit.text()})
        self.close()
        config_data = _load_config()
        if config_data.get("language") == "":
            _show_window(
                self, "open_language_selection_window", mj_language_selection_window
            )
        elif config_data.get("steam_location") == "":
            _show_window(self, "openConfigWindow", mj_steam_location_config_window)
        elif config_data.get("env_location") == "":
            _show_window(
                self, "open_env_location_config_window", mj_env_location_config_window
            )
        else:
            _show_window(self, "open_main_window", MJMainWindow)

    def browse(self):
        folder_path = QFileDialog.getExistingDirectory(
            self, get_string("select_install_location")
        )

        if folder_path:
            if not self.validate_folder(folder_path):
                QMessageBox.warning(self, "MultiJack", get_string("no_installs_error"))
                self.browse()
            else:
                self.set_location_lineedit.setText(folder_path)

    def validate_folder(self, folder_path):
        for root, dirs, files in os.walk(folder_path):
            for dir_name in dirs:
                if any(
                    dir_name.startswith(prefix)
                    for prefix in ["The Jackbox", "Quiplash", "Fibbage", "Drawful"]
                ):
                    return True
        return False


class mj_env_location_config_window(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("MultiJack")
        self.setGeometry(100, 100, 400, 100)

        widget = QWidget(self)
        self.setCentralWidget(widget)

        layout = QVBoxLayout(widget)

        set_location_label = _make_centered_label(
            get_string("select_env_location"), self
        )

        self.set_location_lineedit = QLineEdit(self)
        self.set_location_lineedit.setText(
            os.path.join(get_default_config_location(), "env")
        )

        browseButton = QPushButton(get_string("browse"), self)
        browseButton.clicked.connect(self.browse)

        continue_button = QPushButton(get_string("continue"), self)
        continue_button.clicked.connect(self.setenv_location)

        layout.addWidget(set_location_label)
        layout.addWidget(self.set_location_lineedit)
        layout.addWidget(browseButton)
        layout.addWidget(continue_button)

    def setenv_location(self):
        set_config_option({"env_location": self.set_location_lineedit.text()})
        config_data = _load_config()
        if config_data.get("language") == "":
            _show_window(
                self, "open_language_selection_window", mj_language_selection_window
            )
            self.close()
        elif config_data.get("steam_location") == "":
            _show_window(self, "openConfigWindow", mj_steam_location_config_window)
        elif config_data.get("install_location") == "":
            _show_window(self, "openConfigWindow", mj_install_location_config_window)
        else:
            _show_window(self, "open_main_window", MJMainWindow)
            self.close()

    def browse(self):
        folder_path = QFileDialog.getExistingDirectory(
            self, get_string("select_install_location")
        )

        if folder_path:
            self.set_location_lineedit.setText(folder_path)
