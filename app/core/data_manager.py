import json
import os
from typing import Any, Dict

DATA_FILE = "gamesets.json"


def load_gamesets() -> Dict[str, Any]:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_gamesets(gamesets: Dict[str, Any]) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(gamesets, f, ensure_ascii=False, indent=4)
