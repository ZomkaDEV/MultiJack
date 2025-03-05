version = "1.0.0"

import ctypes
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import uuid
import psutil

from PyQt6.QtCore import Qt, QEvent, QThread, pyqtSignal
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QListWidget, QWidget, QVBoxLayout, QPushButton, \
    QMessageBox, QLineEdit, QFileDialog, QGridLayout, QDialog, QProgressDialog, QInputDialog, QHBoxLayout
# Controller support is only present on Linux right now
if sys.platform == "linux":
    from xbox360controller import Xbox360Controller

games = {
    "The Jackbox Party Pack": 331670,
    "The Jackbox Party Pack 2": 397460,
    "The Jackbox Party Pack 3": 434170,
    "The Jackbox Party Pack 4": 610180,
    "The Jackbox Party Pack 5": 774461,
    "The Jackbox Party Pack 6": 1005300,
    "The Jackbox Party Pack 7": 1211630,
    "The Jackbox Party Pack 8": 1552350,
    "The Jackbox Party Pack 9": 1850960,
    "The Jackbox Party Pack 10": 2216830,
    "The Jackbox Naughty Pack": 2652000,
    "The Jackbox Party Starter": 1755580,
    "The Jackbox Survey Scramble": 2948640,
    "Drawful 2": 442070,
    "Quiplash": 351510,
    "Quiplash 2 InterLASHional": 1111940,
    "Fibbage XL": 448080
}

_localization_cache = None

def load_localization():
    global _localization_cache
    if _localization_cache is None:
        localization_file = os.path.join(os.path.dirname(__file__), 'localization.json')
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            localization_file = os.path.join(sys._MEIPASS, 'localization.json')
        try:
            with open(localization_file, 'r', encoding='utf-8') as file:
                _localization_cache = json.load(file)
        except FileNotFoundError:
            QMessageBox.critical(None, "MultiJack", "Localization file not found!")
            sys.exit(1)
        except json.JSONDecodeError:
            QMessageBox.critical(None, "MultiJack", "Error decoding localization file!")
            sys.exit(1)
    return _localization_cache

def get_string(key):
    localization_data = load_localization()
    return (
        localization_data.get(_selected_language, {}).get(key) or
        localization_data.get("eng", {}).get(key) or
        f"Missing string for key: {key}"
    )

def get_default_steam_location():
    match sys.platform:
        case "win32":
            return "C:\\Program Files (x86)\\Steam\\"
        case "darwin":
            return os.getenv('HOME') + "/Library/Application Support/Steam/"
        case "linux":
            return os.getenv('HOME') + "/.local/share/Steam/"

def get_default_steamapps_location():
    match sys.platform:
        case "win32":
            return "C:\\Program Files (x86)\\Steam\\steamapps\\common\\"
        case "darwin":
            return os.getenv('HOME') + "/Library/Application Support/Steam/steamapps/common/"
        case "linux":
            return os.getenv('HOME') + "/.local/share/Steam/steamapps/common/"

def get_default_config_location():
    match sys.platform:
        case "win32":
            return os.getenv('APPDATA') + "\\MultiJack\\"
        case "darwin":
            return os.getenv('HOME') + "/Library/Application Support/MultiJack/"
        case "linux":
            return os.getenv('HOME') + "/.config/multijack/"

def get_os_name():
    match sys.platform:
        case "win32":
            return "windows"
        case "darwin":
            return "macos"
        case "linux":
            return "linux"

def get_default_game_executable(game):
    match sys.platform:
        case "win32":
            return f"{game}.exe"
        case "darwin":
            return f"{game}.app/Contents/MacOS/{game}"
        case "linux":
            return "Launcher.sh"

def get_default_executable():
    match sys.platform:
        case "win32":
            return ".exe"
        case "darwin":
            return ".app"
        case "linux":
            return ""

def set_config_option(option):
    if not os.path.exists(get_default_config_location()):
        os.makedirs(get_default_config_location())
    if not os.path.isfile(get_default_config_location() + "config.json"):
        with open(get_default_config_location() + "config.json", 'w') as config:
            json.dump({
                "language": "",
                "steam_location": "",
                "install_location": "",
                "env_location": ""
            }, config, indent=4)
    try:
        with open(get_default_config_location() + "config.json", 'r', encoding='utf-8') as file:
            data = json.load(file)
        for key, value in option.items():
            if key in data:
                data[key] = value
            else:
                QMessageBox.critical(None, "MultiJack", f"Requested key is not in config.json!")
                sys.exit(1)
        with open(get_default_config_location() + "config.json", 'w', encoding='utf-8') as config:
            json.dump(data, config, indent=4)
    except FileNotFoundError:
        QMessageBox.critical(None, "MultiJack", f"Configuration file not found!")
        sys.exit(1)
    except json.JSONDecodeError:
        QMessageBox.critical(None, "MultiJack", "Error decoding configuration file!")
        sys.exit(1)


def get_available_envs(game):
    with open(get_default_config_location() + "config.json", 'r', encoding='utf-8') as config_file:
        config_data = json.load(config_file)
    env_path = os.path.join(config_data.get("env_location"), game)

    if not os.path.exists(env_path):
        return [], {}
    envs = []
    env_ids = {}
    for d in os.listdir(env_path):
        env_dir = os.path.join(env_path, d)
        if os.path.isdir(env_dir):
            env_check = os.path.join(env_dir, "DO_NOT_REMOVE.json")
            if os.path.isfile(env_check):
                try:
                    with open(env_check, 'r', encoding='utf-8') as env_info_file:
                        env_info = json.load(env_info_file)
                        env_name = env_info.get("name", d)
                        envs.append(env_name)
                        env_ids[env_name] = d
                except json.JSONDecodeError:
                    envs.append(d)
                    env_ids[d] = d
            else:
                envs.append(d)
                env_ids[d] = d
    return envs, env_ids


class ControllerListener(QThread):
    if sys.platform == "linux":
        hat_signal = pyqtSignal(int)
        button_signal = pyqtSignal()
        exit_signal = pyqtSignal()

        def __init__(self):
            super().__init__()
            self.controller = None

        def run(self):
            try:
                with Xbox360Controller(0, axis_threshold=0.2) as self.controller:
                    self.controller.button_a.when_pressed = self.select_env
                    self.controller.button_b.when_pressed = self.exit_launcher
                    self.controller.hat.when_moved = self.move_up_the_list

                    self.exec()
            except Exception as e:
                logger.error(f"Failed to initialize Xbox 360 controller: {e}")

    def select_env(self, button):
        self.button_signal.emit()

    def exit_launcher(self, button):
        self.exit_signal.emit()

    def move_up_the_list(self, hat):
        if hat.y == 1:
            self.hat_signal.emit(Qt.Key.Key_Up)
        elif hat.y == -1:
            self.hat_signal.emit(Qt.Key.Key_Down)


class LaunchEnvWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MultiJack")
        self.setGeometry(100, 100, 500, 200)

        layout = QVBoxLayout(self)
        self.label = QLabel(get_string("select_env_to_launch"), self)
        layout.addWidget(self.label)

        self.env_list = QListWidget(self)
        self.game = os.path.basename(os.path.dirname(sys.argv[-1]))
        if not self.game:
            logger.error("There's no game specified!")
            sys.exit(1)
        self.envs, self.env_ids = get_available_envs(self.game)
        self.env_list.addItem(get_string("vanilla_game"))
        self.env_list.addItems(self.envs)
        layout.addWidget(self.env_list)

        self.launch_button = QPushButton(get_string("launch_env"), self)
        self.launch_button.clicked.connect(self.launch_environment_button)
        layout.addWidget(self.launch_button)

        self.env_list.setFocus()

        if sys.platform == "linux":
            self.controller_thread = ControllerListener()
            self.controller_thread.hat_signal.connect(self.simulate_key_press)
            self.controller_thread.button_signal.connect(self.launch_environment_button)
            self.controller_thread.exit_signal.connect(QApplication.quit)
            self.controller_thread.start()

    def simulate_key_press(self, key):
        event = QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)
        QApplication.postEvent(self.env_list, event)

    def navigate_menu_controller(self, hat):
        if hat.y == 1:
            self.simulate_key_press(Qt.Key.Key_Up)
        elif hat.y == -1:
            self.simulate_key_press(Qt.Key.Key_Down)

    def launch_environment_button(self):
        selected_env = self.env_list.currentItem()
        if selected_env:
            env_name = selected_env.text()
            env_id = self.env_ids.get(env_name)
            logging.info(f"Launching environment: {env_name} with ID: {env_id}")
            self.launch_environment(env_id)

    def launch_environment(self, env_id):
        if env_id is None:
            logging.info("Launching vanilla game.")
            subprocess.Popen([sys.argv[-1]], cwd=os.path.dirname(sys.argv[-1]), start_new_session=True)
        else:
            env_launcher = os.path.join(get_default_config_location(), "env", self.game, env_id, get_default_game_executable(self.game))
            if not os.path.exists(env_launcher):
                logging.error("Executable not found.")
                QMessageBox.critical(self, "MultiJack", get_string("executable_not_found"))
                return
            logging.info(f"Launching executable: {env_launcher}")
            subprocess.Popen([env_launcher], cwd=os.path.dirname(env_launcher), start_new_session=True)

        self.close()
        QApplication.quit()


class mj_language_selection_window(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("MultiJack")
        self.setGeometry(100, 100, 400, 300)

        widget = QWidget(self)
        self.setCentralWidget(widget)

        layout = QVBoxLayout(widget)

        welcome_label = QLabel("Welcome to MultiJack!\nPlease select your language.", self)
        font = welcome_label.font()
        font.setPointSize(11)
        welcome_label.setFont(font)
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

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
            global _selected_language
            _selected_language = language_code
            set_config_option({"language": language_code})
            self.close()
            with open(get_default_config_location() + "config.json", 'r', encoding='utf-8') as config_file:
                self.config_data = json.load(config_file)
            if self.config_data.get("steam_location") == "":
                self.open_mj_steam_location_config_window = mj_steam_location_config_window()
                self.open_mj_steam_location_config_window.show()
            elif self.config_data.get("install_location") == "":
                self.open_mj_install_location_config_window = mj_install_location_config_window()
                self.open_mj_install_location_config_window.show()
            else:
                self.open_main_window = MJMainWindow()
                self.open_main_window.show()

        else:
            QMessageBox.critical(self, "MultiJack", "Language selection failed.")

class mj_steam_location_config_window(QMainWindow):
    def __init__(self):
        super().__init__()

        with open(get_default_config_location() + "config.json", 'r', encoding='utf-8') as config_file:
            self.config_data = json.load(config_file)

        self.setWindowTitle("MultiJack")
        self.setGeometry(100, 100, 400, 100)

        widget = QWidget(self)
        self.setCentralWidget(widget)

        layout = QVBoxLayout(widget)

        set_location_label = QLabel(get_string("select_steam_location"), self)
        font = set_location_label.font()
        font.setPointSize(11)
        set_location_label.setFont(font)
        set_location_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

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
        if self.config_data.get("language") == "":
            self.open_language_selection_window = mj_language_selection_window()
            self.open_language_selection_window.show()
        elif self.config_data.get("install_location") == "":
            self.open_install_location_config_window = mj_install_location_config_window()
            self.open_install_location_config_window.show()
        elif self.config_data.get("env_location") == "":
            self.open_env_location_config_window = mj_env_location_config_window()
            self.open_env_location_config_window.show()
        else:
            self.open_main_window = MJMainWindow()
            self.open_main_window.show()


    def browse(self):
        folder_path = QFileDialog.getExistingDirectory(self, get_string("select_steam_location"))
        if folder_path:
            if not self.validate_folder(os.path.join(folder_path, "steamapps", "common")):
                QMessageBox.warning(self, "MultiJack", get_string("no_steamapps_installs_error"))
                open_mj_install_location_config_window = mj_install_location_config_window(QMainWindow)
                open_mj_install_location_config_window.show()
            else:
                self.set_location_lineedit.setText(folder_path)

    def validate_folder(self, folder_path):
        root_dirs = [entry for entry in os.listdir(folder_path) if os.path.isdir(os.path.join(folder_path, entry))]

        for dir_name in root_dirs:
            if any(dir_name.startswith(prefix) for prefix in ["The Jackbox", "Quiplash", "Fibbage", "Drawful"]):
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

        with open(get_default_config_location() + "config.json", 'r', encoding='utf-8') as config_file:
            self.config_data = json.load(config_file)

        set_location_label = QLabel(get_string("select_install_location"), self)
        font = set_location_label.font()
        font.setPointSize(11)
        set_location_label.setFont(font)
        set_location_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

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
        if self.config_data.get("language") == "":
            self.open_language_selection_window = mj_language_selection_window()
            self.open_language_selection_window.show()
        elif self.config_data.get("steam_location") == "":
            self.openConfigWindow = mj_steam_location_config_window()
            self.openConfigWindow.show()
        elif self.config_data.get("env_location") == "":
            self.open_env_location_config_window = mj_env_location_config_window()
            self.open_env_location_config_window.show()
        else:
            self.open_main_window = MJMainWindow()
            self.open_main_window.show()


    def browse(self):
        folder_path = QFileDialog.getExistingDirectory(self, get_string("select_install_location"))

        if folder_path:
            if not self.validate_folder(folder_path):
                QMessageBox.warning(self, "MultiJack", get_string("no_installs_error"))
                self.browse()
            else:
                self.set_location_lineedit.setText(folder_path)

    def validate_folder(self, folder_path):
        for root, dirs, files in os.walk(folder_path):
            for dir_name in dirs:
                if any(dir_name.startswith(prefix) for prefix in ["The Jackbox", "Quiplash", "Fibbage", "Drawful"]):
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

        with open(get_default_config_location() + "config.json", 'r', encoding='utf-8') as config_file:
            self.config_data = json.load(config_file)

        set_location_label = QLabel(get_string("select_env_location"), self)
        font = set_location_label.font()
        font.setPointSize(11)
        set_location_label.setFont(font)
        set_location_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.set_location_lineedit = QLineEdit(self)
        self.set_location_lineedit.setText(os.path.join(get_default_config_location(), "env"))

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
        if self.config_data.get("language") == "":
            open_language_selection_window = mj_language_selection_window()
            open_language_selection_window.show()
            self.close()
        elif self.config_data.get("steam_location") == "":
            self.openConfigWindow = mj_steam_location_config_window()
            self.openConfigWindow.show()
        elif self.config_data.get("install_location") == "":
            self.openConfigWindow = mj_install_location_config_window()
            self.openConfigWindow.show()
        else:
            self.open_main_window = MJMainWindow()
            self.open_main_window.show()
            self.close()

    def browse(self):
        folder_path = QFileDialog.getExistingDirectory(self, get_string("select_install_location"))

        if folder_path:
            self.set_location_lineedit.setText(folder_path)

class MJMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        with open(get_default_config_location() + "config.json", 'r', encoding='utf-8') as config_file:
            self.config_data = json.load(config_file)
        self.add_launch_option()

        self.env_dialog = None
        self.about_window = None

        self.setWindowTitle("MultiJack")
        self.setGeometry(100, 100, 500, 200)

        widget = QWidget()
        self.setCentralWidget(widget)
        layout = QVBoxLayout(widget)

        welcome_back_label = QLabel(get_string("welcome_back"), self)
        font = welcome_back_label.font()
        font.setPointSize(11)
        welcome_back_label.setFont(font)
        welcome_back_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(welcome_back_label)

        game_grid = QGridLayout()
        layout.addLayout(game_grid)

        installed_games = []
        for game in os.listdir(self.config_data.get("install_location", [])):
            if os.path.isdir(os.path.join(self.config_data.get("install_location", []), game)) and game in games:
                installed_games.append(game)
        installed_games.sort()

        for index, game in enumerate(installed_games):
            row = index // 3
            col = index % 3

            button = QPushButton(game)
            button.setFixedSize(175, 25)
            button.setStyleSheet("text-align: center; padding: 5px;")
            button.clicked.connect(lambda _, g=game: self.manage_env(g))

            game_grid.addWidget(button, row, col)

        button_layout = QHBoxLayout()

        about_button = QPushButton(get_string("about"), self)
        about_button.setFixedSize(100, 30)
        about_button.clicked.connect(self.open_about_window)
        button_layout.addWidget(about_button)

        button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addLayout(button_layout)

    def open_about_window(self):
        if self.about_window is None or not self.about_window.isVisible():
            self.about_window = QMainWindow(self)
            self.about_window.setWindowTitle("MultiJack")
            self.about_window.setGeometry(150, 150, 400, 200)

            about_widget = QWidget(self.about_window)
            self.about_window.setCentralWidget(about_widget)

            about_layout = QVBoxLayout(about_widget)
            about_label = QLabel("<h2>MultiJack</h2>"
                                 f"{get_string("version")}: {version}<br>"
                                 "<a href=\"https://mj.zomka.dev\">https://mj.zomka.dev</a><br><br>"
                                 f"{get_string("not_affiliated")}<br>"
                                 "Copyright © 2025", self.about_window)
            about_label.setOpenExternalLinks(True)
            about_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            about_layout.addWidget(about_label)

            close_button = QPushButton(get_string("close"), self.about_window)
            close_button.clicked.connect(self.about_window.close)
            about_layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignCenter)

            self.about_window.show()

    def manage_env(self, game):
        if self.env_dialog is not None and self.env_dialog.isVisible():
            self.env_dialog.close()

        self.env_dialog = QDialog(self)
        self.env_dialog.setWindowTitle("MultiJack")
        self.env_dialog.setGeometry(100, 100, 400, 100)

        layout = QVBoxLayout(self.env_dialog)

        game_label = QLabel(self)
        game_label.setText(get_string("game") + ": " + game)

        env_list = QListWidget(self.env_dialog)
        envs_array = self.get_envs(game)
        env_names = {}
        for env in envs_array:
            env_check = os.path.join(self.config_data.get("env_location"), game, env, "DO_NOT_REMOVE.json")
            if os.path.isfile(env_check):
                with open(env_check, 'r', encoding='utf-8') as env_info_file:
                    env_info = json.load(env_info_file)
                env_names[env_info.get("name")] = env
                env_list.addItem(env_info.get("name"))
            else:
                envs_array.remove(env)

        layout.addWidget(game_label)

        layout.addWidget(env_list)

        if len(envs_array) != 0:
            open_folder_button = QPushButton(get_string("open_folder"), self)
            open_folder_button.clicked.connect(lambda: self.open_selected_folder(game, env_list, env_names))
            layout.addWidget(open_folder_button)

            inject_mod_button = QPushButton(get_string("inject_mod_into_env"), self)
            inject_mod_button.clicked.connect(lambda: self.inject_mod_into_selected_env(game, env_list, env_names))
            layout.addWidget(inject_mod_button)

            delete_env_button = QPushButton(get_string("delete_env"), self)
            delete_env_button.clicked.connect(lambda: self.delete_env(game, env_names.get(env_list.currentItem().text()), env_list, env_names))
            layout.addWidget(delete_env_button)
        else:
            env_list.addItem(get_string("no_envs"))

        create_env_button = QPushButton(get_string("create_env"), self)
        create_env_button.clicked.connect(lambda _, g=game: self.create_env(g))
        layout.addWidget(create_env_button)

        self.env_dialog.exec()

    def inject_mod_into_selected_env(self, game, env_list, env_names):
        selected_row = env_list.currentRow()
        if selected_row >= 0:
            selected_name = env_list.item(selected_row).text()
            env_to_inject = env_names.get(selected_name)
            if env_to_inject:
                self.inject_mod_into_env(game, env_to_inject)
            else:
                QMessageBox.warning(self, "MultiJack", get_string("env_not_found_error"))
        else:
            QMessageBox.warning(self, "MultiJack", get_string("select_env_error"))

    def open_selected_folder(self, game, env_list, env_names):
        selected_row = env_list.currentRow()
        if selected_row >= 0:
            selected_name = env_list.item(selected_row).text()
            env_to_open = env_names.get(selected_name)
            if env_to_open:
                folder_path = os.path.join(self.config_data.get("env_location"), game, env_to_open)
                if os.path.exists(folder_path):
                    if os.name == 'nt':
                        os.startfile(folder_path)
                    elif os.name == 'posix':
                        subprocess.Popen(['open', folder_path] if sys.platform == 'darwin' else ['xdg-open', folder_path])
                else:
                    logger.error(f"Folder does not exist: {folder_path}")

    def delete_env(self, game, env, env_list=None, env_names=None):
        env_path = os.path.join(self.config_data.get("env_location"), game, env)

        if os.path.exists(env_path):
            mod_msg = QMessageBox()
            mod_msg.setIcon(QMessageBox.Icon.Information)
            mod_msg.setWindowTitle("MultiJack")
            mod_msg.setText(get_string("do_you_want_to_continue"))
            mod_msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            response = mod_msg.exec()
            if response != QMessageBox.StandardButton.Yes:
                return
            shutil.rmtree(env_path, ignore_errors=True)
            logger.info(f"Deleted environment: {env_path}")
        else:
            logger.warning(f"Environment folder not found: {env_path}")

        if env_list and env_names:
            selected_row = env_list.currentRow()
            if selected_row >= 0:
                env_list.takeItem(selected_row)

        self.manage_env(game)

    def get_envs(self, game):
        if not os.path.exists(self.config_data.get("env_location")):
            os.makedirs(self.config_data.get("env_location"))
        game_env_location = os.path.join(self.config_data.get("env_location"), game)
        if not os.path.exists(game_env_location):
            os.makedirs(game_env_location)

        envs = []
        for entry in os.listdir(game_env_location):
            full_path = os.path.join(game_env_location, entry)
            if os.path.isdir(full_path):
                env_check = os.path.join(full_path, "DO_NOT_REMOVE.json")
                if os.path.isfile(env_check):
                    envs.append(entry)

        return envs

    def is_steam_running(self):
        if sys.platform != "win32":
            steam = "steamwebhelper"
        else:
            steam = "steam.exe"
        for process in psutil.process_iter(["name"]):
            if steam in process.info["name"].lower():
                return True
        return False

    def create_env(self, game):
        env_name, ok = QInputDialog.getText(self, "MultiJack", get_string("name_env"))
        if not ok or not env_name.strip():
            QMessageBox.warning(self, "MultiJack", get_string("invalid_name_env"))
            return
        game_env_location = os.path.join(self.config_data.get("env_location"), game)
        if not os.path.exists(game_env_location):
            os.makedirs(game_env_location)
        env_id = str(uuid.uuid4())
        while os.path.exists(os.path.join(game_env_location, env_id)):
            env_id = str(uuid.uuid4())
        specific_env_location = os.path.join(game_env_location, env_id)
        os.makedirs(specific_env_location)
        self.recreate_directory_structure(os.path.join(self.config_data.get("install_location", []), game), specific_env_location)
        if os.listdir(specific_env_location) != []:
            data = {
                "name": env_name,
                "id": env_id,
                "game": game,
                "version": 0
            }
            with open(os.path.join(specific_env_location, "DO_NOT_REMOVE.json"), 'w') as file:
                json.dump(data, file, indent=4)
            logger.info(f"Config file for env created successfully!")
            success_msg = QMessageBox()
            success_msg.setIcon(QMessageBox.Icon.Information)
            success_msg.setWindowTitle("MultiJack")
            success_msg.setText(get_string("env_creation_passed"))
            success_msg.exec()
            mod_msg = QMessageBox()
            mod_msg.setIcon(QMessageBox.Icon.Information)
            mod_msg.setWindowTitle("MultiJack")
            mod_msg.setText(get_string("env_creation_mod_inject"))
            mod_msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            response = mod_msg.exec()
            if response == QMessageBox.StandardButton.Yes:
                self.inject_mod_into_env(game, env_id)
            self.manage_env(game)

    # Please don't look into these functions unless you actively hate yourself.
    def get_value(self, data, key):
        keys = key.split('.')
        for k in keys:
            if isinstance(data, dict) and k in data:
                data = data[k]
            else:
                return None
        return data

    def set_value(self, data, key, value):
        keys = key.split('.')
        d = data
        for k in keys[:-1]:
            if k not in d or not isinstance(d[k], dict):
                d[k] = {}
            d = d[k]
        d[keys[-1]] = value

    def read_vdf(self, file_path):
        data = {}
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
        stack = [data]
        last_key = None

        for line in lines:
            line = line.strip()
            if not line or line.startswith('//'):
                continue

            if line == '{':
                new_dict = {}
                if last_key is not None:
                    stack[-1][last_key] = new_dict
                stack.append(new_dict)
            elif line == '}':
                stack.pop()
            else:
                match = re.match(r'^"([^"]+)"\s+"(.*)"$', line)
                if match:
                    key, value = match.groups()
                    stack[-1][key] = value
                    last_key = key
                else:
                    last_key = line.strip('"')

        return data

    def save_vdf(self, data, file_path):
        def write_dict(d, indent=0):
            result = ""
            for k, v in d.items():
                if isinstance(v, dict):
                    result += '\t' * (indent // 4) + f'"{k}"\n' + '\t' * (indent // 4) + '{\n' + write_dict(v, indent + 4) + '\t' * (indent // 4) + '}\n'
                else:
                    result += '\t' * (indent // 4) + f'"{k}"\t\t"{v}"\n'
            return result

        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(write_dict(data))

    def add_launch_option(self):
        steam_location = self.config_data.get("steam_location")
        if not os.path.exists(steam_location):
            QMessageBox.critical(None, "MultiJack", get_string("adding_launch_options_failed"))
            return

        userdata_path = os.path.join(steam_location, "userdata")
        if not os.path.exists(userdata_path):
            QMessageBox.critical(None, "MultiJack", get_string("adding_launch_options_failed"))
            return
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            launch_option = re.sub(r"\\", r"\\\\", f"{os.path.abspath(sys.executable)} -launcher %command%")
        else:
            launch_option = re.sub(r"\\", r"\\\\", f"python3 {os.path.abspath(__file__)} -launcher %command%")
            # ^^^ works only if python3 is added to path
            # and if you have the dependencies
            # either way, it's for debugging only

        modified_users = {}

        for user_folder in os.listdir(userdata_path):
            user_config_path = os.path.join(userdata_path, user_folder, "config", "localconfig.vdf")

            if not os.path.exists(user_config_path):
                continue

            try:
                data = self.read_vdf(user_config_path)
                modified = False

                for game, game_id in games.items():
                    launch_options_key = f"UserLocalConfigStore.Software.Valve.Steam.apps.{game_id}.LaunchOptions"
                    existing_value = self.get_value(data, launch_options_key)

                    if existing_value is None or existing_value != launch_option:
                        self.set_value(data, launch_options_key, launch_option)
                        modified = True

                if modified:
                    modified_users[user_folder] = (user_config_path, data)

            except Exception as e:
                logger.error(f"Error reading VDF for user {user_folder}: {e}")

        if not modified_users:
            logger.info("All launch options are already correct. No updates needed.")
            return

        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("MultiJack")
        msg_box.setText(get_string("launch_options_not_empty") + "\n\n" + get_string("do_you_want_to_continue"))
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        response = msg_box.exec()

        if response == QMessageBox.StandardButton.No:
            sys.exit(1)

        while self.is_steam_running():
            close_steam_msg = QMessageBox()
            close_steam_msg.setIcon(QMessageBox.Icon.Warning)
            close_steam_msg.setWindowTitle("MultiJack")
            close_steam_msg.setText(get_string("steam_is_running"))
            close_steam_msg.setStandardButtons(QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel)
            response = close_steam_msg.exec()

            if response == QMessageBox.StandardButton.Cancel:
                sys.exit(1)

        for user_folder, (user_config_path, data) in modified_users.items():
            try:
                self.save_vdf(data, user_config_path)
                logger.info(f"Updated LaunchOptions for user {user_folder}.")
            except Exception as e:
                logger.error(f"Error updating VDF for user {user_folder}: {e}")

        logger.info("Launch options updated where necessary.")

        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setWindowTitle("MultiJack")
        msg_box.setText(get_string("adding_launch_options_success"))
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        response = msg_box.exec()

        if response == QMessageBox.StandardButton.Yes:
            if sys.platform == "win32":
                subprocess.Popen([os.path.join(self.config_data.get("steam_location"), "Steam.exe")], start_new_session=True)
            elif sys.platform == "linux":
                subprocess.Popen(["steam"], start_new_session=True)
            elif sys.platform == "darwin":
                subprocess.Popen(["/Applications/Steam.app/Contents/MacOS/steam_osx"], start_new_session=True)

    def recreate_directory_structure(self, src_dir, dest_dir):
        progress_dialog = QProgressDialog(get_string("processing"), "Cancel", 0, 100, self)
        progress_dialog.setWindowTitle("MultiJack")
        progress_dialog.setMinimumWidth(400)
        progress_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress_dialog.setValue(0)
        progress_dialog.show()

        QApplication.processEvents()

        total_files = sum(len(files) for _, _, files in os.walk(src_dir))
        processed_files = 0
        operation_canceled = False

        for root, dirs, files in os.walk(src_dir):
            rel_path = os.path.relpath(root, src_dir)
            new_dest_dir = os.path.join(dest_dir, rel_path)
            os.makedirs(new_dest_dir, exist_ok=True)

        game = os.path.basename(os.path.normpath(src_dir))
        macos_path = os.path.join(src_dir, f"{game}.app", "Contents", "MacOS", game)

        for root, dirs, files in os.walk(src_dir):
            rel_path = os.path.relpath(root, src_dir)
            new_dest_dir = os.path.join(dest_dir, rel_path)

            for file in files:
                src_file = os.path.abspath(os.path.join(root, file))
                dest_file = os.path.join(new_dest_dir, file)

                if file.endswith("-log.txt"):
                    continue

                try:
                    if sys.platform == "darwin" and os.path.abspath(src_file) == macos_path:
                        if not os.path.exists(dest_file):
                            shutil.copy2(src_file, dest_file)
                            logger.info(f"Copied file: {src_file} -> {dest_file}")
                        else:
                            logger.warning(f"File already exists: {dest_file}")
                    elif sys.platform == "linux" and root == src_dir and (
                            file.endswith("_Vulkan") or file.endswith("_OpenGL")):
                        if not os.path.exists(dest_file):
                            shutil.copy2(src_file, dest_file)
                            logger.info(f"Copied file: {src_file} -> {dest_file}")
                        else:
                            logger.warning(f"File already exists: {dest_file}")
                    else:
                        if not os.path.exists(dest_file):
                            os.symlink(src_file, dest_file)
                            if os.path.islink(dest_file) and os.path.exists(os.readlink(dest_file)):
                                logger.info(f"Symlink created: {dest_file} -> {src_file}")
                            else:
                                logger.error(f"Failed to verify symlink: {dest_file}")
                        else:
                            logger.warning(f"Symlink already exists: {dest_file}")
                except OSError as e:
                    logger.error(f"Error processing file {src_file} -> {dest_file}: {e}")

                processed_files += 1
                progress = int((processed_files / total_files) * 100)
                progress_dialog.setValue(progress)
                progress_dialog.setLabelText(f"{get_string("processing")}: {os.path.basename(src_file)}")

                QApplication.processEvents()

                if progress_dialog.wasCanceled():
                    operation_canceled = True
                    logger.info("Operation canceled by user.")
                    progress_dialog.close()
                    return

        progress_dialog.setValue(100)
        progress_dialog.close()

        if operation_canceled:
            QMessageBox.warning(self, "MultiJack", get_string("env_creation_failed"))

    def inject_mod_into_env(self, game, env_id):
        folder_path = QFileDialog.getExistingDirectory(self, get_string("select_install_location"))

        if not folder_path:
            return

        if not self.validate_folder(folder_path):
            if not sys.platform == "darwin":
                QMessageBox.warning(self, "MultiJack", get_string("not_a_jackbox_mod_error"))
            else:
                QMessageBox.warning(self, "MultiJack", get_string("not_a_jackbox_mod_error_macos"))
            return

        if self.check_folder_for_malicious_stuff(folder_path, game):
            return

        env_path = os.path.join(self.config_data.get("env_location"), game, env_id)

        if sys.platform == "darwin":
            env_path = os.path.join(env_path, f"{game}.app", "Contents", "Resources", "macos")

        if not os.path.exists(env_path):
            QMessageBox.warning(self, "MultiJack", get_string("env_not_found_error"))
            return

        operation_canceled = False
        progress_dialog = QProgressDialog(
            get_string("injecting_files"), "Cancel", 0, 100, self)
        progress_dialog.setWindowTitle("MultiJack")
        progress_dialog.setMinimumWidth(400)
        progress_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress_dialog.setValue(0)
        progress_dialog.show()

        total_files = sum(len(files) for _, _, files in os.walk(folder_path))
        processed_files = 0

        for root, _, files in os.walk(folder_path):
            rel_path = os.path.relpath(root, folder_path)
            dest_dir = os.path.join(env_path, rel_path)
            os.makedirs(dest_dir, exist_ok=True)

            for file in files:
                mod_file = os.path.join(root, file)
                dest_file = os.path.join(dest_dir, file)

                if os.path.islink(dest_file):
                    logger.info(f"Removing existing symlink: {dest_file}")
                    os.unlink(dest_file)

                if os.path.exists(dest_file):
                    try:
                        if not os.path.samefile(mod_file, dest_file):
                            with open(mod_file, 'rb') as f1, open(dest_file, 'rb') as f2:
                                if f1.read() == f2.read():
                                    logger.info(f"Files are identical, skipping: {dest_file}")
                                    continue

                            relative_dest_file = os.path.relpath(dest_file, env_path)

                            response = QMessageBox.question(self, "MultiJack", get_string("mod_replaces_files") + relative_dest_file + "\n" + get_string("do_you_want_to_continue"), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                            if response == QMessageBox.StandardButton.No:
                                logger.info("Skipped conflicting mod")
                                operation_canceled = True
                                break

                            shutil.copy2(mod_file, dest_file)
                            logger.info(f"Overwritten: {relative_dest_file}")
                    except Exception as e:
                        logger.error(f"Error checking or overwriting file {mod_file} -> {dest_file}: {e}")
                else:
                    try:
                        shutil.copy2(mod_file, dest_file)
                        logger.info(f"Copied: {dest_file}")
                    except Exception as e:
                        logger.error(f"Error copying file {mod_file} -> {dest_file}: {e}")

                processed_files += 1
                progress = int((processed_files / total_files) * 100)
                progress_dialog.setValue(progress)
                progress_dialog.setLabelText(f"Processing: {os.path.basename(mod_file)}")

                QApplication.processEvents()

                if progress_dialog.wasCanceled():
                    operation_canceled = True
                    logger.info("Operation canceled by user.")
                    progress_dialog.close()
                    return

        progress_dialog.setValue(100)
        progress_dialog.close()

        if operation_canceled:
            QMessageBox.critical(self, "MultiJack", get_string("mod_injection_failed"))
        else:
            QMessageBox.information(self, "MultiJack", get_string("mod_injection_success"))

    def check_folder_for_malicious_stuff(self, folder_path, game):
        vanilla_game_path = os.path.join(self.config_data.get("install_location", ""), game)

        if not os.path.exists(vanilla_game_path):
            logger.error(f"Vanilla game path not found: {vanilla_game_path}")
            return False

        executable_extensions = {".exe", ".dll", ".sh", ".dylib", "_Vulkan", "_OpenGL"}
        malicious_so_regex = re.compile(r"\.so(\.\d+)?$")

        vanilla_executables = set()
        for root, _, files in os.walk(vanilla_game_path):
            for file in files:
                if any(file.endswith(ext) for ext in executable_extensions) or malicious_so_regex.search(file):
                    relative_path = os.path.relpath(os.path.join(root, file), vanilla_game_path)
                    vanilla_executables.add(relative_path)

        for root, _, files in os.walk(folder_path):
            for file in files:
                if any(file.endswith(ext) for ext in executable_extensions) or malicious_so_regex.search(file):
                    relative_path = os.path.relpath(os.path.join(root, file), folder_path)

                    if relative_path in vanilla_executables:
                        response = QMessageBox.question(
                            self,
                            "MultiJack",
                            f"{get_string("mod_replaces_weird_files")}\n\n'{relative_path}'\n\n{get_string("do_you_want_to_continue")}",
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                        )

                        if response == QMessageBox.StandardButton.No:
                            return True
        return False

    def validate_folder(self, folder_path):
        for root, dirs, files in os.walk(folder_path):
            for dir_name in dirs:
                if any(dir_name.endswith(prefix) for prefix in ["games", "content", "videos"]):
                    return True
            for file_name in files:
                if any(file_name.endswith(prefix) for prefix in [".swf", ".jet", ".json", ".usm", ".swf"]):
                    return True
        return False

    def get_relative_env_path(self, game, env_id):
        install_location = os.path.abspath(self.config_data.get("install_location", "").rstrip("/"))
        env_location = os.path.abspath(os.path.join(self.config_data.get("env_location", ""), game, env_id))

        if not install_location or not env_location:
            raise ValueError("Install location or environment location is not set.")

        relative_path = os.path.relpath(env_location, install_location)
        relative_path = "../" + relative_path
        return relative_path

app = QApplication(sys.argv)
logger = logging.getLogger(__name__)

if "-launcher" in sys.argv:
    with open(get_default_config_location() + "config.json", 'r', encoding='utf-8') as config_file:
        config_data = json.load(config_file)
    logging.basicConfig(filename=os.path.join(get_default_config_location(), "multijacklauncher.log"), encoding='utf-8', level=logging.DEBUG)
    _selected_language = config_data.get("language")
    window = LaunchEnvWindow()
    window.show()
    sys.exit(app.exec())
else:
    try:
        if sys.platform == "win32":
            if not ctypes.windll.shell32.IsUserAnAdmin():
                script = sys.executable
                params = ' '.join([f'"{arg}"' for arg in sys.argv])
                ctypes.windll.shell32.ShellExecuteW(None, "runas", script, params, None, 1)
                sys.exit(0)
        with open(get_default_config_location() + "config.json", 'r', encoding='utf-8') as config_file:
            config_data = json.load(config_file)
        _selected_language = config_data.get("language")
        logging.basicConfig(filename=os.path.join(get_default_config_location(), "multijack.log"), encoding='utf-8', level=logging.DEBUG)
        if config_data.get("language") == "":
            open_language_selection_window = mj_language_selection_window()
            open_language_selection_window.show()
        elif config_data.get("steam_location") == "" or not os.path.exists(config_data.get("steam_location") or not os.listdir(config_data.get("steam_location"))):
            open_steam_location_config_window = mj_steam_location_config_window()
            open_steam_location_config_window.show()
        elif config_data.get("install_location") == "" or not os.path.exists(config_data.get("install_location") or not os.listdir(config_data.get("install_location"))):
            open_install_location_config_window = mj_install_location_config_window()
            open_install_location_config_window.show()
        elif config_data.get("env_location") == "":
            open_env_location_config_window = mj_env_location_config_window()
            open_env_location_config_window.show()
        else:
            open_main_window = MJMainWindow()
            open_main_window.show()
    except FileNotFoundError:
        open_language_selection_window = mj_language_selection_window()
        open_language_selection_window.show()


sys.exit(app.exec())
