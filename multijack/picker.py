import json
from os import path

try:
    from .paths import get_default_config_location
    from .variables import GAMES
except ImportError:  # since i'm still working on it and execute the script directly, i had to add this. it will be removed when i would move on to integrating it with the rest of the codebase.
    import os
    import sys

    sys.path.insert(
        0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    )
    from multijack.paths import get_default_config_location
    from multijack.variables import GAMES


def get_jackbox_lang():
    with open(
        path.join(get_default_config_location(), "config.json"), "r", encoding="utf-8"
    ) as config_file:
        config = json.load(config_file)

    match config.get("language"):
        case "fra":
            return "fr"
        case "deu":
            return "de"
        case "spa":
            return "es"
        case _:
            return "en"


def list_of_games_in_pack(pack_location):
    picker_dir = path.join(pack_location, "games", "Picker")
    content_path = path.join(picker_dir, "content.json")
    if not path.isfile(content_path):
        return []
    try:
        with open(content_path, "r", encoding="utf-8") as content_file:
            data = json.load(content_file)
    except (OSError, json.JSONDecodeError):
        return []

    localization = {}
    localization_en = {}
    language = get_jackbox_lang()
    for loc_name in ("Localization.json", "localization.json"):
        loc_path = path.join(picker_dir, loc_name)
        if path.isfile(loc_path):
            try:
                with open(loc_path, "r", encoding="utf-8") as loc_file:
                    loc_data = json.load(loc_file)
                table = loc_data.get("table", {})
                if isinstance(table, dict) and isinstance(table.get(language), dict):
                    localization = table.get(language, {})
                if isinstance(table, dict) and isinstance(table.get("en"), dict):
                    localization_en = table.get("en", {})
            except (OSError, json.JSONDecodeError):
                localization = {}
                localization_en = {}
            break

    games = []
    for entry in data.get("content", []):
        if not isinstance(entry, dict):
            continue
        if entry.get("enabled") is False:
            continue
        if not entry.get("mainSwf"):
            continue
        if entry.get("name"):
            menu_tag = entry.get("menu")
            tagline_tag = entry.get("tagline")
            games.append(
                {
                    "name": entry.get("name"),
                    "menu_text": localization.get(
                        menu_tag, localization_en.get(menu_tag, menu_tag)
                    ),
                    "tagline_text": localization.get(
                        tagline_tag, localization_en.get(tagline_tag, tagline_tag)
                    ),
                    "mainSwf": entry.get("mainSwf"),
                    "video": entry.get("video"),
                    "audio": entry.get("audio"),
                }
            )
    return games


with open(
    path.join(get_default_config_location(), "config.json"), "r", encoding="utf-8"
) as config_file:
    config = json.load(config_file)

print(
    list_of_games_in_pack(
        os.path.join(config.get("install_location"), "The Jackbox Party Pack 8")
    )
)
