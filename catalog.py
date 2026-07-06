import sqlite3

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


def open_catalog():
    path = current_app.config["BLUEPRINTS_DB_PATH"]
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def row_to_blueprint(row):
    if row is None:
        return None
    return {
        "blueprint_id": row["blueprint_id"],
        "name": row["name"],
        "version": row["version"],
        "game_id": row["game_id"],
        "expansion_name": row["expansion_name"],
        "collector_number": row["collector_number"],
        "image_url": row["image_url"],
    }


def find_blueprint(blueprint_id):
    with open_catalog() as connection:
        row = connection.execute(
            """
            SELECT blueprint_id, name, version, game_id, expansion_name, collector_number, image_url
            FROM blueprints
            WHERE blueprint_id = ?
            """,
            (int(blueprint_id),),
        ).fetchone()
    return row_to_blueprint(row)


def search_blueprints(search_name, partial=False, game_id=None, limit=100):
    if not search_name:
        return []

    where_clauses = []
    parameters = []
    if game_id is not None:
        where_clauses.append("game_id = ?")
        parameters.append(game_id)

    if partial:
        where_clauses.append("lower(name) LIKE ?")
        parameters.append(f"%{search_name.lower()}%")
    else:
        where_clauses.append("lower(name) = ?")
        parameters.append(search_name.lower())

    parameters.append(limit)
    query = f"""
        SELECT blueprint_id, name, version, game_id, expansion_name, collector_number, image_url
        FROM blueprints
        WHERE {" AND ".join(where_clauses)}
        ORDER BY game_id, expansion_name, collector_number
        LIMIT ?
    """

    with open_catalog() as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [row_to_blueprint(row) for row in rows]
