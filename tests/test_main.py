import importlib
import os
from unittest.mock import patch

import pytest

# テスト用にDATA_FILEを上書き
TEST_DATA_FILE = "test_gamesets.json"


@pytest.fixture(autouse=True)
def setup_teardown():
    # テスト開始前にテスト用ファイルを削除
    if os.path.exists(TEST_DATA_FILE):
        os.remove(TEST_DATA_FILE)

    # app.main モジュールをリロードして、モジュールレベルの変数をリセット
    # DATA_FILE のパッチを適用してからリロードする
    with patch("app.main.DATA_FILE", TEST_DATA_FILE):
        # current_gamesets をリセットするためにモジュールをリロード
        # ただし、importlib.reload は既にインポートされているモジュールにのみ作用する
        # そのため、テスト関数内で app.main をインポートする際に最新の状態が反映されるようにする
        # ここでは、current_gamesets を直接クリアするパッチを維持する
        with patch("app.main.current_gamesets", {}):
            yield
            # テスト終了後に current_gamesets を再度クリアして次のテストに影響を与えないようにする
            app_main = importlib.import_module("app.main")
            app_main.current_gamesets.clear()

    # テスト終了後にテスト用ファイルを削除
    if os.path.exists(TEST_DATA_FILE):
        os.remove(TEST_DATA_FILE)


@pytest.mark.asyncio
async def test_start_gameset_logic():
    from app.main import _start_gameset_logic, current_gamesets

    guild_id = "123"
    channel_id = "456"

    success, message = await _start_gameset_logic(guild_id, channel_id)
    assert success is True
    assert (
        message
        == "麻雀のスコア集計を開始します。`/record_game` でゲーム結果を入力してください。"
    )
    assert current_gamesets[guild_id][channel_id]["status"] == "active"
    assert current_gamesets[guild_id][channel_id]["games"] == []
    assert current_gamesets[guild_id][channel_id]["members"] == {}

    # 既に進行中のゲームセットがある場合のテスト
    success, message = await _start_gameset_logic(guild_id, channel_id)
    assert success is False
    assert message == "すでにこのチャンネルでゲームセットが進行中です。"


@pytest.mark.asyncio
async def test_record_game_logic_success():
    from app.main import _record_game_logic, _start_gameset_logic, current_gamesets

    guild_id = "123"
    channel_id = "456"

    # ゲームセットを開始
    await _start_gameset_logic(guild_id, channel_id)

    # 4人麻雀の成功ケース
    success, message = await _record_game_logic(
        guild_id,
        channel_id,
        rule="hanchan",
        players_count=4,
        scores_str="@player1:25000,@player2:15000,@player3:-10000,@player4:-30000",
    )
    assert success is True
    expected_message = "ゲーム結果を記録しました。\n@player1: 25000 (1着), @player2: 15000 (2着), @player3: -10000 (3着), @player4: -30000 (4着)"
    assert message == expected_message
    assert len(current_gamesets[guild_id][channel_id]["games"]) == 1
    assert current_gamesets[guild_id][channel_id]["members"]["player1"] == 25000
    assert current_gamesets[guild_id][channel_id]["members"]["player2"] == 15000
    assert current_gamesets[guild_id][channel_id]["members"]["player3"] == -10000
    assert current_gamesets[guild_id][channel_id]["members"]["player4"] == -30000

    # 別のゲームを追加
    success, message = await _record_game_logic(
        guild_id,
        channel_id,
        rule="tonpu",
        players_count=4,
        scores_str="@player1:10000,@player2:0,@player3:-5000,@player4:-5000",
    )
    assert success is True
    expected_message = "ゲーム結果を記録しました。\n@player1: 10000 (1着), @player2: 0 (2着), @player3: -5000 (3着), @player4: -5000 (4着)"
    assert message == expected_message
    assert len(current_gamesets[guild_id][channel_id]["games"]) == 2
    assert current_gamesets[guild_id][channel_id]["members"]["player1"] == 35000
    assert current_gamesets[guild_id][channel_id]["members"]["player2"] == 15000
    assert current_gamesets[guild_id][channel_id]["members"]["player3"] == -15000
    assert current_gamesets[guild_id][channel_id]["members"]["player4"] == -35000

    # サンマの成功ケース
    success, message = await _record_game_logic(
        guild_id,
        channel_id,
        rule="hanchan",
        players_count=3,
        scores_str="@playerA:30000,@playerB:0,@playerC:-30000",
    )
    assert success is True
    expected_message = "ゲーム結果を記録しました。\n@playerA: 30000 (1着), @playerB: 0 (2着), @playerC: -30000 (3着)"
    assert message == expected_message
    assert len(current_gamesets[guild_id][channel_id]["games"]) == 3
    assert current_gamesets[guild_id][channel_id]["members"]["playerA"] == 30000
    assert current_gamesets[guild_id][channel_id]["members"]["playerB"] == 0
    assert current_gamesets[guild_id][channel_id]["members"]["playerC"] == -30000


@pytest.mark.asyncio
async def test_record_game_logic_validation_errors():
    from app.main import _record_game_logic, _start_gameset_logic

    guild_id = "123"
    channel_id = "456"

    # ゲームセットが開始されていない場合
    success, message = await _record_game_logic(
        guild_id,
        channel_id,
        rule="hanchan",
        players_count=4,
        scores_str="@p1:0,@p2:0,@p3:0,@p4:0",
    )
    assert success is False
    assert (
        message
        == "このチャンネルで進行中のゲームセットがありません。`/start_gameset` で開始してください。"
    )

    await _start_gameset_logic(guild_id, channel_id)

    # 無効なルール
    success, message = await _record_game_logic(
        guild_id,
        channel_id,
        rule="invalid",
        players_count=4,
        scores_str="@p1:0,@p2:0,@p3:0,@p4:0",
    )
    assert success is False
    assert (
        message
        == "ルールは 'tonpu' (東風戦) または 'hanchan' (半荘戦) で指定してください。"
    )

    # 無効な人数
    success, message = await _record_game_logic(
        guild_id,
        channel_id,
        rule="hanchan",
        players_count=0,
        scores_str="@p1:0,@p2:0,@p3:0,@p4:0",
    )
    assert success is False
    assert message == "参加人数は 3 (サンマ) または 4 (4人) で指定してください。"

    # スコアの数が不足 (ヨンマで3人)
    success, message = await _record_game_logic(
        guild_id,
        channel_id,
        rule="hanchan",
        players_count=4,
        scores_str="@p1:0,@p2:0,@p3:0",
    )
    assert success is False
    assert (
        message
        == "4人分のスコアを入力してください。現在 3人分のスコアが入力されています。"
    )

    # スコアの形式が不正 (値が数値でない)
    success, message = await _record_game_logic(
        guild_id,
        channel_id,
        rule="hanchan",
        players_count=4,
        scores_str="@p1:abc,@p2:0,@p3:0,@p4:0",
    )
    assert success is False
    assert (
        message
        == "スコアの形式が正しくありません。`名前:スコア` の形式で入力してください (例: `@player1:25000`)。"
    )

    # スコアの形式が不正 (コロンがない)
    success, message = await _record_game_logic(
        guild_id,
        channel_id,
        rule="hanchan",
        players_count=4,
        scores_str="@p1 10000,@p2:0,@p3:0,@p4:0",
    )
    assert success is False
    assert (
        message
        == "スコアの形式が正しくありません。`名前:スコア` の形式で入力してください (例: `@player1:25000`)。"
    )

    # ゼロサムチェック失敗
    success, message = await _record_game_logic(
        guild_id,
        channel_id,
        rule="hanchan",
        players_count=4,
        scores_str="@p1:10000,@p2:0,@p3:0,@p4:0",
    )
    assert success is False
    assert (
        message
        == "スコアの合計が0になりません。現在の合計: 10000。再入力してください。"
    )

    # 重複するプレイヤー名
    success, message = await _record_game_logic(
        guild_id,
        channel_id,
        rule="hanchan",
        players_count=4,
        scores_str="@p1:10000,@p1:0,@p3:0,@p4:-10000",
    )
    assert success is False
    assert (
        message
        == "プレイヤー名 'p1' が重複しています。異なるプレイヤー名を入力してください。"
    )


@pytest.mark.asyncio
async def test_end_gameset_logic():
    from app.main import (
        _end_gameset_logic,
        _record_game_logic,
        _start_gameset_logic,
        current_gamesets,
    )

    guild_id = "123"
    channel_id = "456"

    # ゲームセットが開始されていない場合
    success, message = await _end_gameset_logic(guild_id, channel_id)
    assert success is False
    assert message == "このチャンネルで進行中のゲームセットがありません。"

    # ゲームセットを開始
    await _start_gameset_logic(guild_id, channel_id)

    # ゲームを記録
    await _record_game_logic(
        guild_id,
        channel_id,
        rule="hanchan",
        players_count=4,
        scores_str="@player1:25000,@player2:15000,@player3:-10000,@player4:-30000",
    )

    await _record_game_logic(
        guild_id,
        channel_id,
        rule="tonpu",
        players_count=4,
        scores_str="@player1:10000,@player2:0,@player3:-5000,@player4:-5000",
    )

    # ゲームセットを終了
    success, message = await _end_gameset_logic(guild_id, channel_id)
    assert success is True
    expected_message = (
        "## 麻雀ゲームセット結果\n"
        "- player1: 35000\n"
        "- player2: 15000\n"
        "- player3: -15000\n"
        "- player4: -35000\n"
    )
    assert message == expected_message
    assert current_gamesets[guild_id][channel_id]["status"] == "inactive"

    # 記録されたゲームがない場合
    current_gamesets[guild_id][channel_id] = {
        "status": "active",
        "games": [],
        "members": {},
    }
    success, message = await _end_gameset_logic(guild_id, channel_id)
    assert success is False
    assert message == "記録されたゲームがありません。"
