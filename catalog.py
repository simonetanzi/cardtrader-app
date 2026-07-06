import sqlite3

from flask import current_app


MAGIC_GAME_ID = 1
MAGIC_GAME_NAME = "Magic: the Gathering"

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
        "rarity": row["rarity"],
        "image_url": row["image_url"],
    }


def find_blueprint(blueprint_id):
    with open_catalog() as connection:
        row = connection.execute(
            """
            SELECT blueprint_id, name, version, game_id, expansion_name, collector_number, rarity, image_url
            FROM blueprints
            WHERE blueprint_id = ?
            """,
            (int(blueprint_id),),
        ).fetchone()
    return row_to_blueprint(row)


def search_blueprints(search_name, partial=False, limit=100):
    if not search_name:
        return []

    where_clauses = ["game_id = ?"]
    parameters = [MAGIC_GAME_ID]

    if partial:
        where_clauses.append("lower(name) LIKE ?")
        parameters.append(f"%{search_name.lower()}%")
    else:
        where_clauses.append("lower(name) = ?")
        parameters.append(search_name.lower())

    parameters.append(limit)
    query = f"""
        SELECT blueprint_id, name, version, game_id, expansion_name, collector_number, rarity, image_url
        FROM blueprints
        WHERE {" AND ".join(where_clauses)}
        ORDER BY game_id, expansion_name, collector_number
        LIMIT ?
    """

    with open_catalog() as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [row_to_blueprint(row) for row in rows]
