import json
import logging
import os
import shlex
import shutil
import subprocess
import sys
import uuid

import psutil
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import env_ops, vdf
from .config import add_launch_options_to_env
from .localization import get_string
from .paths import get_default_config_location
from .variables import GAMES, VERSION

logger = logging.getLogger(__name__)


class MJMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        with open(
            os.path.join(get_default_config_location(), "config.json"),
            "r",
            encoding="utf-8",
        ) as config_file:
            self.config_data = json.load(config_file)

        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            self.add_launch_option()
        else:
            logger.warning(
                "Hi, you know why this is triggered. If not, you don't understand what you're doing."
            )

        self.env_dialog = None
        self.about_window = None

        self.setWindowTitle("MultiJack")
        self.setGeometry(100, 100, 600, 200)

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
            if (
                os.path.isdir(
                    os.path.join(self.config_data.get("install_location", []), game)
                )
                and game in GAMES
            ):
                installed_games.append(game)
        installed_games.sort()

        for index, game in enumerate(installed_games):
            row = index // 3
            col = index % 3

            button = QPushButton(game)
            button.setFixedSize(190, 32)
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
            about_label = QLabel(
                "<h2>MultiJack</h2>"
                f"{get_string('version')}: {VERSION}<br>"
                '<a href="https://mj.zomka.dev">https://mj.zomka.dev</a><br><br>'
                f"{get_string('not_affiliated')}<br>"
                "Copyright © 2025",
                self.about_window,
            )
            about_label.setOpenExternalLinks(True)
            about_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            about_layout.addWidget(about_label)

            reset_config_button = QPushButton(
                get_string("reset_config"), self.about_window
            )
            reset_config_button.clicked.connect(self.reset_config)
            about_layout.addWidget(
                reset_config_button, alignment=Qt.AlignmentFlag.AlignCenter
            )

            close_button = QPushButton(get_string("close"), self.about_window)
            close_button.clicked.connect(self.about_window.close)
            about_layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignCenter)

            self.about_window.show()

    def reset_config(self):
        first_confirm = QMessageBox.question(
            self,
            "MultiJack",
            get_string("do_you_want_to_continue"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if first_confirm != QMessageBox.StandardButton.Yes:
            return

        delete_envs_confirm = QMessageBox.question(
            self,
            "MultiJack",
            get_string("delete_all_envs"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if delete_envs_confirm == QMessageBox.StandardButton.Yes:
            double_confirm = QMessageBox.question(
                self,
                "MultiJack",
                get_string("delete_all_envs_confirmation"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if double_confirm == QMessageBox.StandardButton.Yes:
                env_path = self.config_data.get("env_location")
                try:
                    if os.path.exists(env_path):
                        shutil.rmtree(env_path)
                        logger.info(f"Deleted all environments at {env_path}")
                        QMessageBox.information(
                            self, "MultiJack", get_string("delete_all_envs_success")
                        )
                except Exception as e:
                    logger.error(f"Failed to delete envs: {e}")
                    QMessageBox.critical(
                        self,
                        "MultiJack",
                        f"{get_string('something_went_wrong').replace('%LOGFILELOCATION%', os.path.join(get_default_config_location(), 'multijack.log'))}{e}",
                    )
                    return
        try:
            if os.path.exists(os.path.join(get_default_config_location())):
                # Windows will complain that it can't delete the log file because it's in use
                for handler in logger.handlers[:]:
                    handler.close()
                    logger.removeHandler(handler)
                logging.shutdown()

                shutil.rmtree(os.path.join(get_default_config_location()))
                QMessageBox.information(
                    self, "MultiJack", get_string("reset_config_success")
                )
        except Exception as e:
            QMessageBox.critical(
                self,
                "MultiJack",
                f"{get_string('something_went_wrong').replace('%LOGFILELOCATION%', os.path.join(get_default_config_location(), 'multijack.log'))}{e}",
            )
        QApplication.quit()

    def manage_env(self, game):
        if self.env_dialog is not None and self.env_dialog.isVisible():
            self.env_dialog.close()

        self.env_dialog = QDialog(self)
        self.env_dialog.setWindowTitle("MultiJack")
        self.env_dialog.setGeometry(100, 100, 400, 150)

        self.launch_options_dialog = None

        layout = QVBoxLayout(self.env_dialog)

        game_label = QLabel(self)
        game_label.setText(get_string("game") + ": " + game)

        env_list = QListWidget(self.env_dialog)
        envs_array = self.get_envs(game)
        env_names = {}
        env_list.addItem(get_string("vanilla_game"))
        for env in envs_array:
            env_check = os.path.join(
                self.config_data.get("env_location"), game, env, "DO_NOT_REMOVE.json"
            )
            if os.path.isfile(env_check):
                with open(env_check, "r", encoding="utf-8") as env_info_file:
                    env_info = json.load(env_info_file)
                env_names[env_info.get("name")] = env
                env_list.addItem(env_info.get("name"))
            else:
                envs_array.remove(env)

        layout.addWidget(game_label)

        layout.addWidget(env_list)

        open_folder_button = QPushButton(get_string("open_folder"), self)
        open_folder_button.clicked.connect(
            lambda: self.open_selected_folder(game, env_list, env_names)
        )
        layout.addWidget(open_folder_button)

        if len(envs_array) > 0:
            inject_mod_button = QPushButton(get_string("inject_mod_into_env"), self)
            inject_mod_button.clicked.connect(
                lambda: self.inject_mod_into_selected_env(game, env_list, env_names)
            )
            layout.addWidget(inject_mod_button)

            delete_env_button = QPushButton(get_string("delete_env"), self)
            delete_env_button.clicked.connect(
                lambda: self.delete_env(
                    game,
                    env_names.get(env_list.currentItem().text()),
                    env_list,
                    env_names,
                )
            )
            layout.addWidget(delete_env_button)

        add_launch_options_to_env_button = QPushButton(
            get_string("change_launch_options"), self
        )
        add_launch_options_to_env_button.clicked.connect(
            lambda: self.add_launch_options_to_env_dialog(game, env_list, env_names)
        )
        layout.addWidget(add_launch_options_to_env_button)

        create_env_button = QPushButton(get_string("create_env"), self)
        create_env_button.clicked.connect(lambda _, g=game: self.create_env(g))
        layout.addWidget(create_env_button)

        self.env_dialog.exec()

    def add_launch_options_to_env_dialog(self, game, env_list, env_names):
        if (
            self.launch_options_dialog is None
            or not self.launch_options_dialog.isVisible()
        ):
            selected_row = env_list.currentRow()
            if selected_row >= 0:
                selected_name = env_list.item(selected_row).text()
                env_to_be_modified = env_names.get(selected_name)

                if env_to_be_modified is None:
                    env_to_be_modified = ""
                self.env_config_location = os.path.join(
                    self.config_data.get("env_location"),
                    game,
                    env_to_be_modified,
                    "DO_NOT_REMOVE.json",
                )
                current_launch_options = ""
                if os.path.exists(self.env_config_location):
                    current_launch_options = json.load(
                        open(self.env_config_location, "r")
                    ).get("launch_options")

                if env_to_be_modified or selected_name == get_string("vanilla_game"):
                    self.launch_options_dialog = QDialog(self)
                    self.launch_options_dialog.setWindowTitle("MultiJack")
                    self.launch_options_dialog.setGeometry(100, 100, 400, 100)

                    game_label = QLabel(self)
                    game_label.setText(get_string("launch_options"))

                    self.set_launch_options_lineedit = QLineEdit(self)
                    self.set_launch_options_lineedit.setText(current_launch_options)

                    close_button = QPushButton(get_string("close"), self)
                    close_button.clicked.connect(self.launch_options_dialog.close)

                    add_launch_options_to_env_layout = QVBoxLayout(
                        self.launch_options_dialog
                    )
                    add_launch_options_to_env_layout.addWidget(game_label)
                    add_launch_options_to_env_layout.addWidget(
                        self.set_launch_options_lineedit
                    )
                    add_launch_options_to_env_layout.addWidget(close_button)
                    self.launch_options_dialog.finished.connect(
                        self.add_launch_options_dialog_handler
                    )
                    self.launch_options_dialog.exec()
                else:
                    QMessageBox.warning(
                        self, "MultiJack", get_string("env_not_found_error")
                    )
            else:
                QMessageBox.warning(self, "MultiJack", get_string("select_env_error"))

    def add_launch_options_dialog_handler(self):
        add_launch_options_to_env(
            self.env_config_location, self.set_launch_options_lineedit.text()
        )

    def inject_mod_into_selected_env(self, game, env_list, env_names):
        selected_row = env_list.currentRow()
        if selected_row >= 0:
            selected_name = env_list.item(selected_row).text()
            env_to_inject = env_names.get(selected_name)
            if env_to_inject:
                env_ops.inject_mod_into_env(
                    game,
                    env_to_inject,
                    self.config_data,
                    self,
                    logger,
                )
            elif selected_name == get_string("vanilla_game"):
                QMessageBox.warning(
                    self, "MultiJack", get_string("cant_modify_vanilla")
                )
            else:
                QMessageBox.warning(
                    self, "MultiJack", get_string("env_not_found_error")
                )
        else:
            QMessageBox.warning(self, "MultiJack", get_string("select_env_error"))

    def open_selected_folder(self, game, env_list, env_names):
        selected_row = env_list.currentRow()
        if selected_row >= 0:
            selected_name = env_list.item(selected_row).text()
            env_to_open = env_names.get(selected_name)
            vanilla_folder_path = os.path.join(
                self.config_data.get("install_location"), game
            )
            if env_to_open:
                env_folder_path = os.path.join(
                    self.config_data.get("env_location"), game, env_to_open
                )
                if os.path.exists(env_folder_path):
                    if os.name == "nt":
                        os.startfile(env_folder_path)
                    elif os.name == "posix":
                        subprocess.Popen(
                            ["open", env_folder_path]
                            if sys.platform == "darwin"
                            else ["xdg-open", env_folder_path]
                        )
                else:
                    logger.error("Folder does not exist.")
            elif os.path.exists(vanilla_folder_path):
                if os.name == "nt":
                    os.startfile(vanilla_folder_path)
                elif os.name == "posix":
                    subprocess.Popen(
                        ["open", vanilla_folder_path]
                        if sys.platform == "darwin"
                        else ["xdg-open", vanilla_folder_path]
                    )

    def delete_env(self, game, env, env_list=None, env_names=None):
        if env is None:
            QMessageBox.warning(self, "MultiJack", get_string("cant_delete_vanilla"))
            return
        env_path = os.path.join(self.config_data.get("env_location"), game, env)

        if os.path.exists(env_path):
            mod_msg = QMessageBox()
            mod_msg.setIcon(QMessageBox.Icon.Information)
            mod_msg.setWindowTitle("MultiJack")
            mod_msg.setText(get_string("do_you_want_to_continue"))
            mod_msg.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
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
        match sys.platform:
            case "win32":
                steam = "steam.exe"
            case "darwin":
                steam = "steam_osx"
            case "linux":
                steam = "steamwebhelper"
        for process in psutil.process_iter(["name"]):
            if steam in process.info["name"].lower():
                return True
        return False

    def create_env(self, game):
        env_name, ok = QInputDialog.getText(self, "MultiJack", get_string("name_env"))
        if not ok or not env_name.strip() or env_name == game:
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
        env_ops.recreate_directory_structure(
            os.path.join(self.config_data.get("install_location", []), game),
            specific_env_location,
            self,
            logger,
        )
        if os.listdir(specific_env_location) != []:
            data = {"name": env_name, "id": env_id, "game": game, "version": 0}
            with open(
                os.path.join(specific_env_location, "DO_NOT_REMOVE.json"), "w"
            ) as file:
                json.dump(data, file, indent=4)
            logger.info("Config file for env created successfully!")
            success_msg = QMessageBox()
            success_msg.setIcon(QMessageBox.Icon.Information)
            success_msg.setWindowTitle("MultiJack")
            success_msg.setText(get_string("env_creation_passed"))
            success_msg.exec()
            mod_msg = QMessageBox()
            mod_msg.setIcon(QMessageBox.Icon.Information)
            mod_msg.setWindowTitle("MultiJack")
            mod_msg.setText(get_string("env_creation_mod_inject"))
            mod_msg.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            response = mod_msg.exec()
            if response == QMessageBox.StandardButton.Yes:
                env_ops.inject_mod_into_env(
                    game,
                    env_id,
                    self.config_data,
                    self,
                    logger,
                )
            self.manage_env(game)

    def add_launch_option(self):
        steam_location = self.config_data.get("steam_location")
        if not os.path.exists(steam_location):
            QMessageBox.critical(
                None, "MultiJack", get_string("adding_launch_options_failed")
            )
            return

        userdata_path = os.path.join(steam_location, "userdata")
        if not os.path.exists(userdata_path):
            QMessageBox.critical(
                None, "MultiJack", get_string("adding_launch_options_failed")
            )
            return
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            executable = os.path.abspath(sys.executable)
        else:
            executable = f"python3 {os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, 'main.py'))}"
            # ^^^ works only if python3 is added to path
            # and if you have the dependencies
            # either way, it's for debugging only

        if os.name == "nt":
            quoted_executable = f'"{executable.replace("\\", "\\\\")}"'.replace(
                '"', '\\"'
            )
        else:
            quoted_executable = shlex.quote(executable)

        launch_option = f"{quoted_executable} -launcher %command%"

        modified_users = {}

        for user_folder in os.listdir(userdata_path):
            user_config_path = os.path.join(
                userdata_path, user_folder, "config", "localconfig.vdf"
            )

            if not os.path.exists(user_config_path):
                continue

            try:
                data = vdf.read_vdf(user_config_path)
                modified = False

                for game, game_id in GAMES.items():
                    launch_options_key = f"UserLocalConfigStore.Software.Valve.Steam.apps.{game_id}.LaunchOptions"
                    existing_value = vdf.get_value(data, launch_options_key)

                    if existing_value is None or existing_value != launch_option:
                        vdf.set_value(data, launch_options_key, launch_option)
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
        msg_box.setText(
            get_string("launch_options_not_empty")
            + "\n\n"
            + get_string("do_you_want_to_continue")
        )
        msg_box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        response = msg_box.exec()

        if response == QMessageBox.StandardButton.No:
            sys.exit(1)

        while self.is_steam_running():
            close_steam_msg = QMessageBox()
            close_steam_msg.setIcon(QMessageBox.Icon.Warning)
            close_steam_msg.setWindowTitle("MultiJack")
            close_steam_msg.setText(get_string("steam_is_running"))
            close_steam_msg.setStandardButtons(
                QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel
            )
            response = close_steam_msg.exec()

            if response == QMessageBox.StandardButton.Cancel:
                sys.exit(1)

        for user_folder, (user_config_path, data) in modified_users.items():
            try:
                vdf.save_vdf(data, user_config_path)
                logger.info(f"Updated LaunchOptions for user {user_folder}.")
            except Exception as e:
                logger.error(f"Error updating VDF for user {user_folder}: {e}")

        logger.info("Launch options updated where necessary.")

        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setWindowTitle("MultiJack")
        msg_box.setText(get_string("adding_launch_options_success"))
        msg_box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        response = msg_box.exec()

        if response == QMessageBox.StandardButton.Yes:
            if sys.platform == "win32":
                subprocess.Popen(
                    [os.path.join(self.config_data.get("steam_location"), "Steam.exe")],
                    start_new_session=True,
                )
            elif sys.platform == "linux":
                subprocess.Popen(["steam"], start_new_session=True)
            elif sys.platform == "darwin":
                subprocess.Popen(
                    ["/Applications/Steam.app/Contents/MacOS/steam_osx"],
                    start_new_session=True,
                )

    def get_relative_env_path(self, game, env_id):
        install_location = os.path.abspath(
            self.config_data.get("install_location", "").rstrip("/")
        )
        env_location = os.path.abspath(
            os.path.join(self.config_data.get("env_location", ""), game, env_id)
        )

        if not install_location or not env_location:
            raise ValueError("Install location or environment location is not set.")

        relative_path = os.path.relpath(env_location, install_location)
        relative_path = "../" + relative_path
        return relative_path
