import json
import os
import sys

from PyQt6.QtWidgets import QMessageBox

from . import state


def load_localization():
    if state.localization_cache is None:
        base_dir = os.path.dirname(os.path.dirname(__file__))
        localization_file = os.path.join(base_dir, 'localization.json')
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            localization_file = os.path.join(sys._MEIPASS, 'localization.json')
        try:
            with open(localization_file, 'r', encoding='utf-8') as file:
                state.localization_cache = json.load(file)
        except FileNotFoundError:
            QMessageBox.critical(None, "MultiJack", "Localization file not found!")
            sys.exit(1)
        except json.JSONDecodeError:
            QMessageBox.critical(None, "MultiJack", "Error decoding localization file!")
            sys.exit(1)
    return state.localization_cache


def get_string(key):
    localization_data = load_localization()
    return (
        localization_data.get(state.selected_language, {}).get(key)
        or localization_data.get("eng", {}).get(key)
        or f"Missing string for key: {key}"
    )
