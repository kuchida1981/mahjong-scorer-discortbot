import os
from unittest.mock import patch

import pytest

from app.core.models import Gameset, GamesetsRoot

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
        # Pydanticモデルの初期化方法に合わせて変更
        gameset_manager.current_gamesets = GamesetsRoot()

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
    assert gameset_manager.current_gamesets[guild_id][channel_id].status == "active"
    assert gameset_manager.current_gamesets[guild_id][channel_id].games == []
    assert gameset_manager.current_gamesets[guild_id][channel_id].members == {}

    # 既に進行中のゲームセットがある場合のテスト
    success, message = gameset_manager.start_gameset(guild_id, channel_id)
    assert success is True
    assert message == "既存のゲームセットを破棄し、新しい麻雀のスコア集計を開始します。"
    assert gameset_manager.current_gamesets[guild_id][channel_id].status == "active"
    assert gameset_manager.current_gamesets[guild_id][channel_id].games == []
    assert gameset_manager.current_gamesets[guild_id][channel_id].members == {}


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
    assert len(gameset_manager.current_gamesets[guild_id][channel_id].games) == 1
    assert (
        gameset_manager.current_gamesets[guild_id][channel_id].games[0].service
        == "tenhou"
    )
    assert (
        gameset_manager.current_gamesets[guild_id][channel_id].members["player1"]
        == 25000
    )
    assert (
        gameset_manager.current_gamesets[guild_id][channel_id].members["player2"]
        == 15000
    )
    assert (
        gameset_manager.current_gamesets[guild_id][channel_id].members["player3"]
        == -10000
    )
    assert (
        gameset_manager.current_gamesets[guild_id][channel_id].members["player4"]
        == -30000
    )

    # 別のゲームを追加 (service指定なし、デフォルトjantama)
    success, message, sorted_scores = gameset_manager.record_game(
        guild_id,
        channel_id,
        rule="tonpu",
        players_count=4,
        scores_str="@player1:10000,@player2:0,@player3:-5000,@player4:-5000",
        service="jantama",
    )
    assert success is True
    assert message == "ゲーム結果を記録しました。"
    assert sorted_scores == [
        ("player1", 10000),
        ("player2", 0),
        ("player3", -5000),
        ("player4", -5000),
    ]
    assert len(gameset_manager.current_gamesets[guild_id][channel_id].games) == 2
    assert (
        gameset_manager.current_gamesets[guild_id][channel_id].games[1].service
        == "jantama"
    )
    assert (
        gameset_manager.current_gamesets[guild_id][channel_id].members["player1"]
        == 35000
    )
    assert (
        gameset_manager.current_gamesets[guild_id][channel_id].members["player2"]
        == 15000
    )
    assert (
        gameset_manager.current_gamesets[guild_id][channel_id].members["player3"]
        == -15000
    )
    assert (
        gameset_manager.current_gamesets[guild_id][channel_id].members["player4"]
        == -35000
    )

    # サンマの成功ケース
    success, message, sorted_scores = gameset_manager.record_game(
        guild_id,
        channel_id,
        rule="hanchan",
        players_count=3,
        scores_str="@playerA:30000,@playerB:0,@playerC:-30000",
        service="jantama",
    )
    assert success is True
    assert message == "ゲーム結果を記録しました。"
    assert sorted_scores == [
        ("playerA", 30000),
        ("playerB", 0),
        ("playerC", -30000),
    ]
    assert len(gameset_manager.current_gamesets[guild_id][channel_id].games) == 3
    assert (
        gameset_manager.current_gamesets[guild_id][channel_id].games[2].service
        == "jantama"
    )
    assert (
        gameset_manager.current_gamesets[guild_id][channel_id].members["playerA"]
        == 30000
    )
    assert (
        gameset_manager.current_gamesets[guild_id][channel_id].members["playerB"] == 0
    )
    assert (
        gameset_manager.current_gamesets[guild_id][channel_id].members["playerC"]
        == -30000
    )


@pytest.mark.asyncio
async def test_record_game_logic_validation_errors(setup_teardown):
    gameset_manager = setup_teardown
    guild_id = "123"
    channel_id = "456"

    # ゲームセットが開始されていない場合
    success, message, _ = gameset_manager.record_game(
        guild_id,
        channel_id,
        rule="hanchan",
        players_count=4,
        scores_str="@p1:0,@p2:0,@p3:0,@p4:0",
        service="jantama",
    )
    assert success is False
    assert message == "このチャンネルで進行中のゲームセットがありません。"

    gameset_manager.start_gameset(guild_id, channel_id)

    # スコアの数が不足 (ヨンマで3人)
    success, message, _ = gameset_manager.record_game(
        guild_id,
        channel_id,
        rule="hanchan",
        players_count=4,
        scores_str="@p1:0,@p2:0,@p3:0",
        service="jantama",
    )
    assert success is False
    assert (
        message
        == "4人分のスコアを入力してください。現在 3人分のスコアが入力されています。"
    )

    # スコアの形式が不正 (値が数値でない)
    success, message, _ = gameset_manager.record_game(
        guild_id,
        channel_id,
        rule="hanchan",
        players_count=4,
        scores_str="@p1:abc,@p2:0,@p3:0,@p4:0",
        service="jantama",
    )
    assert success is False
    assert (
        message
        == "スコアの形式が正しくありません。`名前:スコア` の形式で入力してください (例: `@player1:25000`)。"
    )

    # スコアの形式が不正 (コロンがない)
    success, message, _ = gameset_manager.record_game(
        guild_id,
        channel_id,
        rule="hanchan",
        players_count=4,
        scores_str="@p1 10000,@p2:0,@p3:0,@p4:0",
        service="jantama",
    )
    assert success is False
    assert (
        message
        == "スコアの形式が正しくありません。`名前:スコア` の形式で入力してください (例: `@player1:25000`)。"
    )

    # ゼロサムチェック失敗
    success, message, _ = gameset_manager.record_game(
        guild_id,
        channel_id,
        rule="hanchan",
        players_count=4,
        scores_str="@p1:10000,@p2:0,@p3:0,@p4:0",
        service="jantama",
    )
    assert success is False
    assert (
        message
        == "スコアの合計が0になりません。現在の合計: 10000。再入力してください。"
    )

    # 重複するプレイヤー名
    success, message, _ = gameset_manager.record_game(
        guild_id,
        channel_id,
        rule="hanchan",
        players_count=4,
        scores_str="@p1:10000,@p1:0,@p3:0,@p4:-10000",
        service="jantama",
    )
    assert success is False
    assert (
        message
        == "プレイヤー名 'p1' が重複しています。異なるプレイヤー名を入力してください。"
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
    assert gameset_manager.current_gamesets[guild_id][channel_id].status == "inactive"

    # 記録されたゲームがない場合
    gameset_manager.current_gamesets[guild_id][channel_id] = Gameset(
        status="active", games=[], members={}
    )
    success, message, _ = gameset_manager.end_gameset(guild_id, channel_id)
    assert success is True
    assert message == "ゲームセットを閉じました。記録されたゲームはありませんでした。"
    assert gameset_manager.current_gamesets[guild_id][channel_id].status == "inactive"
    assert gameset_manager.current_gamesets[guild_id][channel_id].games == []
    assert gameset_manager.current_gamesets[guild_id][channel_id].members == {}
