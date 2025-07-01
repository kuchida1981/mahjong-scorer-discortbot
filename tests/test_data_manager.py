import json
import os
from unittest.mock import patch

import pytest

from app.core.models import Gameset, GamesetsRoot

# テスト用にDATA_FILEを上書き
TEST_DATA_FILE = "test_gamesets.json"


@pytest.fixture(autouse=True)
def setup_teardown_data_manager():
    # テスト開始前にテスト用ファイルを削除
    if os.path.exists(TEST_DATA_FILE):
        os.remove(TEST_DATA_FILE)
    yield
    # テスト終了後にテスト用ファイルを削除
    if os.path.exists(TEST_DATA_FILE):
        os.remove(TEST_DATA_FILE)


def test_load_gamesets_file_not_exists(setup_teardown_data_manager):
    from app.core.data_manager import load_gamesets

    with patch("app.core.data_manager.DATA_FILE", TEST_DATA_FILE):
        gamesets = load_gamesets()
        assert isinstance(gamesets, GamesetsRoot)
        assert gamesets.root == {}


def test_load_gamesets_file_exists(setup_teardown_data_manager):
    from app.core.data_manager import load_gamesets

    test_data = {
        "guild1": {"channel1": {"status": "active", "games": [], "members": {}}}
    }
    with patch("app.core.data_manager.DATA_FILE", TEST_DATA_FILE):
        with open(TEST_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(test_data, f)
        gamesets = load_gamesets()
        assert isinstance(gamesets, GamesetsRoot)
        assert gamesets["guild1"]["channel1"].status == "active"
        assert isinstance(gamesets["guild1"]["channel1"], Gameset)


def test_save_gamesets(setup_teardown_data_manager):
    from app.core.data_manager import save_gamesets

    test_gamesets_root = GamesetsRoot()
    test_gamesets_root["guild1"] = {
        "channel1": Gameset(status="active", games=[], members={})
    }
    with patch("app.core.data_manager.DATA_FILE", TEST_DATA_FILE):
        save_gamesets(test_gamesets_root)
        with open(TEST_DATA_FILE, "r", encoding="utf-8") as f:
            loaded_data = json.load(f)
        assert loaded_data == {
            "guild1": {"channel1": {"status": "active", "games": [], "members": {}}}
        }
