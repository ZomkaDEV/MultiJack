import json
import logging
import os
import subprocess
import sys

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from . import state
from .config import get_available_envs
from .controller import ControllerListener
from .localization import get_string
from .paths import get_default_config_location, get_default_game_executable

logger = logging.getLogger(__name__)


class LaunchEnvWindow(QDialog):
    def __init__(self):
        super().__init__()

        self.game = os.path.basename(os.path.dirname(sys.argv[-1]))
        self.envs, self.env_ids = get_available_envs(self.game)
        if len(self.envs) == 0:
            self.launch_environment(None)
            sys.exit(1)

        self.setWindowTitle("MultiJack")
        self.setGeometry(100, 100, 500, 200)

        layout = QVBoxLayout(self)
        self.label = QLabel(get_string("select_env_to_launch"), self)
        layout.addWidget(self.label)

        self.env_list = QListWidget(self)
        if not self.game:
            logger.error("There's no game specified!")
            sys.exit(1)
        if state.temp_launch and isinstance(state.temp_launch, (list, tuple)):
            if len(state.temp_launch) >= 1 and state.temp_launch[0] == self.game:
                env_to_launch = (
                    state.temp_launch[1] if len(state.temp_launch) >= 2 else None
                )
                logger.info(f"Silently launching {self.game} (env: {env_to_launch})")
                self.launch_environment(env_to_launch)
                sys.exit(1)
        else:
            logger.info("Preparing env selection...")
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
        with open(
            os.path.join(get_default_config_location(), "config.json"),
            "r",
            encoding="utf-8",
        ) as config_file:
            config_data = json.load(config_file)
        if env_id is None:
            env_id = ""
        env_config_location = os.path.join(
            config_data.get("env_location"), self.game, env_id, "DO_NOT_REMOVE.json"
        )
        current_launch_options = ""
        if state.temp_launch and isinstance(state.temp_launch, (list, tuple)):
            if len(state.temp_launch) >= 3 and state.temp_launch[2]:
                current_launch_options = state.temp_launch[2]
        elif os.path.exists(env_config_location):
            env_config = json.load(open(env_config_location, "r"))
            if env_config.get("launch_options"):
                current_launch_options = env_config.get("launch_options")
        if env_id == "":
            logging.info("Launching vanilla game.")
            if current_launch_options != "":
                logging.info(f"Launch options: {current_launch_options}")
            subprocess.Popen(
                [
                    os.path.join(
                        os.path.dirname(sys.argv[-1]),
                        get_default_game_executable(self.game),
                    )
                ]
                + current_launch_options.split(),
                cwd=os.path.dirname(sys.argv[-1]),
                start_new_session=True,
            )
        else:
            env_launcher = os.path.join(
                config_data.get("env_location"),
                self.game,
                env_id,
                get_default_game_executable(self.game),
            )
            if not os.path.exists(env_launcher):
                logging.error("Executable not found.")
                QMessageBox.critical(
                    self, "MultiJack", get_string("executable_not_found")
                )
                return
            logging.info(f"Launching executable: {env_launcher}")
            subprocess.Popen(
                [env_launcher] + current_launch_options.split(),
                cwd=os.path.dirname(env_launcher),
                start_new_session=True,
            )

        self.close()
        QApplication.quit()
