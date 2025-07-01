import json
import os

from app.core.models import GamesetsRoot

DATA_FILE = "gamesets.json"


def load_gamesets() -> GamesetsRoot:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return GamesetsRoot.model_validate(data)
    return GamesetsRoot(root={})


def save_gamesets(gamesets: GamesetsRoot) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(gamesets.model_dump(by_alias=True), f, ensure_ascii=False, indent=4)
