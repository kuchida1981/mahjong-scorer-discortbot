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

    # app.core.data_manager.DATA_FILE をパッチ
    with patch("app.core.data_manager.DATA_FILE", TEST_DATA_FILE):
        # GamesetManager の current_gamesets をリセットするためにモジュールをリロード
        # ただし、importlib.reload は既にインポートされているモジュールにのみ作用する
        # そのため、テスト関数内で app.core.gameset_manager をインポートする際に最新の状態が反映されるようにする
        # ここでは、GamesetManager のインスタンスを新しく作成することで対応する
        from app.core.gameset_manager import GamesetManager

        gameset_manager = GamesetManager()
        gameset_manager.current_gamesets.clear()  # 念のためクリア

        yield gameset_manager

    # テスト終了後にテスト用ファイルを削除
    if os.path.exists(TEST_DATA_FILE):
        os.remove(TEST_DATA_FILE)


@pytest.mark.asyncio
async def test_start_gameset_logic(setup_teardown):
    gameset_manager = setup_teardown
    guild_id = "123"
    channel_id = "456"

    # 新規ゲームセット開始のテスト
    success, message = gameset_manager.start_gameset(guild_id, channel_id)
    assert success is True
    assert message == "麻雀のスコア集計を開始します。"
    assert gameset_manager.current_gamesets[guild_id][channel_id]["status"] == "active"
    assert gameset_manager.current_gamesets[guild_id][channel_id]["games"] == []
    assert gameset_manager.current_gamesets[guild_id][channel_id]["members"] == {}

    # 既に進行中のゲームセットがある場合のテスト
    success, message = gameset_manager.start_gameset(guild_id, channel_id)
    assert success is True
    assert message == "既存のゲームセットを破棄し、新しい麻雀のスコア集計を開始します。"
    assert gameset_manager.current_gamesets[guild_id][channel_id]["status"] == "active"
    assert gameset_manager.current_gamesets[guild_id][channel_id]["games"] == []
    assert gameset_manager.current_gamesets[guild_id][channel_id]["members"] == {}


@pytest.mark.asyncio
async def test_add_member_logic(setup_teardown):
    gameset_manager = setup_teardown
    guild_id = "123"
    channel_id = "456"

    gameset_manager.start_gameset(guild_id, channel_id)

    # メンバー追加の成功ケース
    success, message = gameset_manager.add_member(guild_id, channel_id, "playerA")
    assert success is True
    assert message == "メンバー 'playerA' を登録しました。"
    assert (
        "playerA" in gameset_manager.current_gamesets[guild_id][channel_id]["members"]
    )
    assert (
        gameset_manager.current_gamesets[guild_id][channel_id]["members"]["playerA"]
        == 0
    )

    # メンバー重複の失敗ケース
    success, message = gameset_manager.add_member(guild_id, channel_id, "playerA")
    assert success is False
    assert message == "メンバー 'playerA' は既に登録されています。"


@pytest.mark.asyncio
async def test_get_members_logic(setup_teardown):
    gameset_manager = setup_teardown
    guild_id = "123"
    channel_id = "456"

    gameset_manager.start_gameset(guild_id, channel_id)

    # メンバーがいない場合
    success, message, members = gameset_manager.get_members(guild_id, channel_id)
    assert success is False
    assert message == "登録されているメンバーがいません。"
    assert members is None

    # メンバーを追加
    gameset_manager.add_member(guild_id, channel_id, "playerA")
    gameset_manager.add_member(guild_id, channel_id, "playerB")

    # メンバーがいる場合
    success, message, members = gameset_manager.get_members(guild_id, channel_id)
    assert success is True
    assert message == "登録メンバー一覧"
    assert sorted(members) == sorted(["playerA", "playerB"])


@pytest.mark.asyncio
async def test_record_game_logic_success(setup_teardown):
    gameset_manager = setup_teardown
    guild_id = "123"
    channel_id = "456"

    # ゲームセットを開始
    gameset_manager.start_gameset(guild_id, channel_id)

    # 4人麻雀の成功ケース (service指定あり)
    success, message, sorted_scores = gameset_manager.record_game(
        guild_id,
        channel_id,
        rule="hanchan",
        players_count=4,
        scores_str="@player1:25000,@player2:15000,@player3:-10000,@player4:-30000",
        service="tenhou",
    )
    assert success is True
    assert message == "ゲーム結果を記録しました。"
    assert sorted_scores == [
        ("player1", 25000),
        ("player2", 15000),
        ("player3", -10000),
        ("player4", -30000),
    ]
    assert len(gameset_manager.current_gamesets[guild_id][channel_id]["games"]) == 1
    assert (
        gameset_manager.current_gamesets[guild_id][channel_id]["games"][0]["service"]
        == "tenhou"
    )


@pytest.mark.asyncio
async def test_current_scores_logic(setup_teardown):
    gameset_manager = setup_teardown
    guild_id = "123"
    channel_id = "456"

    # ゲームセットが開始されていない場合
    success, message, _ = gameset_manager.get_current_scores(guild_id, channel_id)
    assert success is False
    assert message == "このチャンネルで進行中のゲームセットがありません。"

    gameset_manager.start_gameset(guild_id, channel_id)

    # まだゲームが記録されていない場合
    success, message, _ = gameset_manager.get_current_scores(guild_id, channel_id)
    assert success is False
    assert message == "まだゲームが記録されていません。"

    # ゲームを記録
    gameset_manager.record_game(
        guild_id,
        channel_id,
        rule="hanchan",
        players_count=4,
        scores_str="@player1:25000,@player2:15000,@player3:-10000,@player4:-30000",
        service="jantama",
    )

    success, message, sorted_scores = gameset_manager.get_current_scores(
        guild_id, channel_id
    )
    assert success is True
    assert message == "現在のトータルスコア"
    assert sorted_scores == [
        ("player1", 25000),
        ("player2", 15000),
        ("player3", -10000),
        ("player4", -30000),
    ]

    gameset_manager.record_game(
        guild_id,
        channel_id,
        rule="tonpu",
        players_count=4,
        scores_str="@player1:10000,@player2:0,@player3:-5000,@player4:-5000",
        service="tenhou",
    )

    success, message, sorted_scores = gameset_manager.get_current_scores(
        guild_id, channel_id
    )
    assert success is True
    assert message == "現在のトータルスコア"
    assert sorted_scores == [
        ("player1", 35000),
        ("player2", 15000),
        ("player3", -15000),
        ("player4", -35000),
    ]


@pytest.mark.asyncio
async def test_end_gameset_logic(setup_teardown):
    gameset_manager = setup_teardown
    guild_id = "123"
    channel_id = "456"

    # ゲームセットが開始されていない場合
    success, message, _ = gameset_manager.end_gameset(guild_id, channel_id)
    assert success is False
    assert message == "このチャンネルで進行中のゲームセットがありません。"

    # ゲームセットを開始
    gameset_manager.start_gameset(guild_id, channel_id)

    # ゲームを記録
    gameset_manager.record_game(
        guild_id,
        channel_id,
        rule="hanchan",
        players_count=4,
        scores_str="@player1:25000,@player2:15000,@player3:-10000,@player4:-30000",
        service="jantama",
    )

    gameset_manager.record_game(
        guild_id,
        channel_id,
        rule="tonpu",
        players_count=4,
        scores_str="@player1:10000,@player2:0,@player3:-5000,@player4:-5000",
        service="tenhou",
    )

    # ゲームセットを終了
    success, message, sorted_scores = gameset_manager.end_gameset(guild_id, channel_id)
    assert success is True
    assert message == "麻雀ゲームセット結果"
    assert sorted_scores == [
        ("player1", 35000),
        ("player2", 15000),
        ("player3", -15000),
        ("player4", -35000),
    ]
    assert (
        gameset_manager.current_gamesets[guild_id][channel_id]["status"] == "inactive"
    )

    # 記録されたゲームがない場合
    gameset_manager.current_gamesets[guild_id][channel_id] = {
        "status": "active",
        "games": [],
        "members": {},
    }
    success, message, _ = gameset_manager.end_gameset(guild_id, channel_id)
    assert success is True
    assert message == "ゲームセットを閉じました。記録されたゲームはありませんでした。"
    assert (
        gameset_manager.current_gamesets[guild_id][channel_id]["status"] == "inactive"
    )
    assert gameset_manager.current_gamesets[guild_id][channel_id]["games"] == []
    assert gameset_manager.current_gamesets[guild_id][channel_id]["members"] == {}
