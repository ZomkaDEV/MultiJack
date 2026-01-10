import json
import os
import sys

from PyQt6.QtWidgets import QMessageBox

from .paths import get_default_config_location
from .variables import GAMES


def set_config_option(option):
    if not os.path.exists(get_default_config_location()):
        os.makedirs(get_default_config_location())
    if not os.path.isfile(os.path.join(get_default_config_location(), "config.json")):
        with open(
            os.path.join(get_default_config_location(), "config.json"), "w"
        ) as config:
            json.dump(
                {
                    "language": "",
                    "steam_location": "",
                    "install_location": "",
                    "env_location": "",
                },
                config,
                indent=4,
            )
    try:
        with open(
            os.path.join(get_default_config_location(), "config.json"),
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)
        for key, value in option.items():
            data[key] = value
        with open(
            os.path.join(get_default_config_location(), "config.json"),
            "w",
            encoding="utf-8",
        ) as config:
            json.dump(data, config, indent=4)
    except FileNotFoundError:
        QMessageBox.critical(None, "MultiJack", "Configuration file not found!")
        sys.exit(1)
    except json.JSONDecodeError:
        QMessageBox.critical(None, "MultiJack", "Error decoding configuration file!")
        sys.exit(1)


def get_available_envs(game):
    with open(
        os.path.join(get_default_config_location(), "config.json"),
        "r",
        encoding="utf-8",
    ) as config_file:
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
                    with open(env_check, "r", encoding="utf-8") as env_info_file:
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


def add_launch_options_to_env(env_config_location, launch_options):
    if env_config_location is not None:
        if os.path.basename(os.path.dirname(env_config_location)) in GAMES:
            vanilla_env_config = {"vanilla": True, "launch_options": launch_options}
            with open(env_config_location, "w") as file:
                json.dump(vanilla_env_config, file, indent=4)
        elif os.path.exists(env_config_location):
            with open(env_config_location, "r") as file:
                env_config = json.load(file)
            env_config["launch_options"] = launch_options
            with open(env_config_location, "w") as file:
                json.dump(env_config, file, indent=4)
