import json
import gzip
from functools import lru_cache

from flask import current_app


GAMES = [
    {"id": None, "display_name": "All games"},
    {"id": 1, "display_name": "Magic: the Gathering"},
    {"id": 4, "display_name": "Yu-Gi-Oh!"},
    {"id": 5, "display_name": "Pokemon"},
    {"id": 6, "display_name": "Flesh and Blood"},
    {"id": 8, "display_name": "Digimon"},
    {"id": 9, "display_name": "Dragon Ball Super"},
    {"id": 10, "display_name": "Cardfight!! Vanguard"},
    {"id": 15, "display_name": "One Piece"},
    {"id": 18, "display_name": "Disney Lorcana"},
    {"id": 20, "display_name": "Star Wars Unlimited"},
    {"id": 21, "display_name": "Union Arena"},
    {"id": 22, "display_name": "Riftbound | League of Legends"},
    {"id": 23, "display_name": "Gundam"},
    {"id": 24, "display_name": "Sorcery: Contested Realm"},
]

LANGUAGES = [
    ("it", "IT"),
    ("en", "EN"),
    ("de", "DE"),
    ("es", "ES"),
    ("fr", "FR"),
    ("pt", "PT"),
    ("ru", "RU"),
    ("jp", "JP"),
    ("kr", "KR"),
    ("zh-CN", "ZH-CN"),
    ("zh-TW", "ZH-TW"),
]

CONDITIONS = [
    "Mint",
    "Near Mint",
    "Slightly Played",
    "Moderately Played",
    "Played",
    "Heavily Played",
    "Poor",
]

CONDITION_RANK = {
    "Mint": 0,
    "Near Mint": 1,
    "Slightly Played": 2,
    "Moderately Played": 3,
    "Played": 4,
    "Heavily Played": 5,
    "Poor": 6,
}

DEFAULT_LANGUAGES = ["en"]
DEFAULT_MINIMUM_CONDITION = "Moderately Played"


@lru_cache(maxsize=1)
def load_blueprints():
    path = current_app.config["BLUEPRINTS_DB_PATH"]
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as file:
        data = json.load(file)
    return data.get("blueprints", [])


def find_blueprint(blueprint_id):
    wanted = int(blueprint_id)
    for blueprint in load_blueprints():
        if blueprint.get("blueprint_id") == wanted:
            return blueprint
    return None


def matches_card_name(blueprint, search_name, partial):
    name = blueprint.get("name", "")
    if partial:
        return search_name.lower() in name.lower()
    return name.lower() == search_name.lower()


def search_blueprints(search_name, partial=False, game_id=None, limit=100):
    if not search_name:
        return []

    matches = []
    for blueprint in load_blueprints():
        if game_id is not None and blueprint.get("game_id") != game_id:
            continue
        if matches_card_name(blueprint, search_name, partial):
            matches.append(blueprint)
            if len(matches) >= limit:
                break

    matches.sort(
        key=lambda bp: (
            str(bp.get("game_id") or ""),
            str(bp.get("expansion_name") or ""),
            str(bp.get("collector_number") or ""),
        )
    )
    return matches
