import os
import sys


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
