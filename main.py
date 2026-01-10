import ctypes
import json
import logging
import os
import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

from multijack import state
from multijack.config import set_config_option
from multijack.launch_window import LaunchEnvWindow
from multijack.main_window import MJMainWindow
from multijack.paths import get_default_config_location
from multijack.setup_windows import (
    mj_env_location_config_window,
    mj_install_location_config_window,
    mj_language_selection_window,
    mj_steam_location_config_window,
)
from multijack.variables import GAMES

app = QApplication(sys.argv)
logger = logging.getLogger(__name__)

# log get big. space wasted.
if os.path.exists(os.path.join(get_default_config_location(), "multijack.log")):
    os.remove(os.path.join(get_default_config_location(), "multijack.log"))


def get_arg_value(flag):
    if flag in sys.argv:
        index = sys.argv.index(flag)
        if index + 1 < len(sys.argv):
            return sys.argv[index + 1]
    return None


if "-launch" in sys.argv:
    with open(
        os.path.join(get_default_config_location(), "config.json"),
        "r",
        encoding="utf-8",
    ) as config_file:
        config_data = json.load(config_file)
    logging.basicConfig(
        filename=os.path.join(get_default_config_location(), "multijacklaunch.log"),
        encoding="utf-8",
        level=logging.DEBUG,
    )
    game = get_arg_value("-launch")
    env = get_arg_value("-env")
    launch_options = get_arg_value("-launch_options")
    if os.path.exists(os.path.join(config_data.get("install_location"), game)):
        if env:
            if not os.path.exists(
                os.path.join(config_data.get("env_location"), game, env)
            ):
                logger.error(f"Environment {env} does not exist!")
        set_config_option({"temp_launch": [game, env, launch_options]})
        match sys.platform:
            case "win32":
                os.system(f"start steam://launch/{GAMES.get(game)}")
            case "darwin":
                os.system(f"open steam://launch/{GAMES.get(game)}")
            case "linux":
                os.system(f"xdg-open steam://launch/{GAMES.get(game)}")
    sys.exit(0)

elif "-launcher" in sys.argv:
    if not os.path.exists(os.path.join(get_default_config_location(), "config.json")):
        QMessageBox.critical(
            None, "MultiJack", "Your config file was not found! Please open MultiJack!"
        )
        sys.exit(1)
    with open(
        os.path.join(get_default_config_location(), "config.json"),
        "r",
        encoding="utf-8",
    ) as config_file:
        config_data = json.load(config_file)
    logging.basicConfig(
        filename=os.path.join(get_default_config_location(), "multijacklauncher.log"),
        encoding="utf-8",
        level=logging.DEBUG,
    )
    state.selected_language = config_data.get("language")
    if config_data.get("temp_launch"):
        state.temp_launch = config_data.get("temp_launch")
        set_config_option({"temp_launch": []})
    window = LaunchEnvWindow()
    window.show()
    sys.exit(app.exec())
else:
    try:
        if sys.platform == "win32":
            if not ctypes.windll.shell32.IsUserAnAdmin():
                script = sys.executable
                params = " ".join([f'"{arg}"' for arg in sys.argv])
                ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", script, params, None, 1
                )
                sys.exit(0)
        with open(
            os.path.join(get_default_config_location(), "config.json"),
            "r",
            encoding="utf-8",
        ) as config_file:
            config_data = json.load(config_file)
        state.selected_language = config_data.get("language")
        logging.basicConfig(
            filename=os.path.join(get_default_config_location(), "multijack.log"),
            encoding="utf-8",
            level=logging.DEBUG,
        )
        if config_data.get("language") == "":
            open_language_selection_window = mj_language_selection_window()
            open_language_selection_window.show()
        elif config_data.get("steam_location") == "" or not os.path.exists(
            config_data.get("steam_location")
            or not os.listdir(config_data.get("steam_location"))
        ):
            open_steam_location_config_window = mj_steam_location_config_window()
            open_steam_location_config_window.show()
        elif config_data.get("install_location") == "" or not os.path.exists(
            config_data.get("install_location")
            or not os.listdir(config_data.get("install_location"))
        ):
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
