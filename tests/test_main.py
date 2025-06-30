import importlib
import os
from unittest.mock import AsyncMock, patch

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
            # interaction のモックを作成
            mock_interaction = AsyncMock()
            mock_guild = AsyncMock()
            mock_interaction.guild = mock_guild

            # テストで使用するプレイヤー名に対応するモックメンバーを作成
            mock_member_player1 = AsyncMock()
            mock_member_player1.nick = "player1"
            mock_member_player1.name = "player1"
            mock_member_player1.mention = "<@111111111111111111>"  # 適当なID

            mock_member_player2 = AsyncMock()
            mock_member_player2.nick = "player2"
            mock_member_player2.name = "player2"
            mock_member_player2.mention = "<@222222222222222222>"

            mock_member_player3 = AsyncMock()
            mock_member_player3.nick = "player3"
            mock_member_player3.name = "player3"
            mock_member_player3.mention = "<@333333333333333333>"

            mock_member_player4 = AsyncMock()
            mock_member_player4.nick = "player4"
            mock_member_player4.name = "player4"
            mock_member_player4.mention = "<@444444444444444444>"

            mock_member_playerA = AsyncMock()
            mock_member_playerA.nick = "playerA"
            mock_member_playerA.name = "playerA"
            mock_member_playerA.mention = "<@AAAAAAAAAAAAAAA>"

            mock_member_playerB = AsyncMock()
            mock_member_playerB.nick = "playerB"
            mock_member_playerB.name = "playerB"
            mock_member_playerB.mention = "<@BBBBBBBBBBBBBBB>"

            mock_member_playerC = AsyncMock()
            mock_member_playerC.nick = "playerC"
            mock_member_playerC.name = "playerC"
            mock_member_playerC.mention = "<@CCCCCCCCCCCCCCC>"

            mock_member_p1 = AsyncMock()
            mock_member_p1.nick = "p1"
            mock_member_p1.name = "p1"
            mock_member_p1.mention = "<@P1P1P1P1P1P1P1P1>"

            mock_member_p2 = AsyncMock()
            mock_member_p2.nick = "p2"
            mock_member_p2.name = "p2"
            mock_member_p2.mention = "<@P2P2P2P2P2P2P2P2>"

            mock_member_p3 = AsyncMock()
            mock_member_p3.nick = "p3"
            mock_member_p3.name = "p3"
            mock_member_p3.mention = "<@P3P3P3P3P3P3P3P3>"

            mock_member_p4 = AsyncMock()
            mock_member_p4.nick = "p4"
            mock_member_p4.name = "p4"
            mock_member_p4.mention = "<@P4P4P4P4P4P4P4P4>"

            mock_guild.members = [
                mock_member_player1,
                mock_member_player2,
                mock_member_player3,
                mock_member_player4,
                mock_member_playerA,
                mock_member_playerB,
                mock_member_playerC,
                mock_member_p1,
                mock_member_p2,
                mock_member_p3,
                mock_member_p4,
            ]

            # yield にモックを渡す
            yield mock_interaction
            # テスト終了後に current_gamesets を再度クリアして次のテストに影響を与えないようにする
            app_main = importlib.import_module("app.main")
            app_main.current_gamesets.clear()

    # テスト終了後にテスト用ファイルを削除
    if os.path.exists(TEST_DATA_FILE):
        os.remove(TEST_DATA_FILE)


@pytest.mark.asyncio
async def test_start_gameset_logic(setup_teardown):
    from app.main import _start_gameset_logic, current_gamesets

    guild_id = "123"
    channel_id = "456"
    mock_interaction = setup_teardown

    # 新規ゲームセット開始のテスト
    success, message = await _start_gameset_logic(
        guild_id, channel_id, mock_interaction
    )
    assert success is True
    assert (
        message
        == "麻雀のスコア集計を開始します。`/mj_record` でゲーム結果を入力してください。"
    )
    assert current_gamesets[guild_id][channel_id]["status"] == "active"
    assert current_gamesets[guild_id][channel_id]["games"] == []
    assert current_gamesets[guild_id][channel_id]["members"] == {}

    # 既に進行中のゲームセットがある場合のテスト (確認ダイアログで「はい」を選択)
    mock_interaction.response.send_message.reset_mock()  # モックをリセット
    mock_interaction.response.edit_message.reset_mock()  # モックをリセット

    # ConfirmStartGamesetView のインスタンスをモックし、value を True に設定
    with patch("app.main.ConfirmStartGamesetView", autospec=True) as MockView:
        mock_view_instance = MockView.return_value
        mock_view_instance.value = True  # 「はい」を選択したと仮定
        mock_view_instance.wait = AsyncMock()  # wait メソッドをモック

        success, message = await _start_gameset_logic(
            guild_id, channel_id, mock_interaction
        )

        MockView.assert_called_once_with(guild_id, channel_id)
        mock_interaction.response.send_message.assert_called_once_with(
            "すでにこのチャンネルでゲームセットが進行中です。現在のゲームセットを破棄して、新しいゲームセットを開始しますか？",
            view=mock_view_instance,
            ephemeral=True,
        )
        mock_view_instance.wait.assert_called_once()
        assert success is True
        assert (
            message
            == "既存のゲームセットを破棄し、新しい麻雀のスコア集計を開始します。`/mj_record` でゲーム結果を入力してください。"
        )
        assert current_gamesets[guild_id][channel_id]["status"] == "active"
        assert current_gamesets[guild_id][channel_id]["games"] == []
        assert current_gamesets[guild_id][channel_id]["members"] == {}

    # 既に進行中のゲームセットがある場合のテスト (確認ダイアログで「いいえ」を選択)
    mock_interaction.response.send_message.reset_mock()  # モックをリセット
    mock_interaction.response.edit_message.reset_mock()  # モックをリセット

    with patch("app.main.ConfirmStartGamesetView", autospec=True) as MockView:
        mock_view_instance = MockView.return_value
        mock_view_instance.value = False  # 「いいえ」を選択したと仮定
        mock_view_instance.wait = AsyncMock()  # wait メソッドをモック

        success, message = await _start_gameset_logic(
            guild_id, channel_id, mock_interaction
        )

        MockView.assert_called_once_with(guild_id, channel_id)
        mock_interaction.response.send_message.assert_called_once_with(
            "すでにこのチャンネルでゲームセットが進行中です。現在のゲームセットを破棄して、新しいゲームセットを開始しますか？",
            view=mock_view_instance,
            ephemeral=True,
        )
        mock_view_instance.wait.assert_called_once()
        assert success is False
        assert message == "新しいゲームセットの開始をキャンセルしました。"
        assert (
            current_gamesets[guild_id][channel_id]["status"] == "active"
        )  # キャンセルなので状態は変わらない


@pytest.mark.asyncio
async def test_record_game_logic_success(setup_teardown):
    from app.main import (_record_game_logic, _start_gameset_logic,
                          current_gamesets)

    guild_id = "123"
    channel_id = "456"
    mock_interaction = setup_teardown

    # ゲームセットを開始
    await _start_gameset_logic(guild_id, channel_id, mock_interaction)

    # 4人麻雀の成功ケース (service指定あり)
    success, message = await _record_game_logic(
        guild_id,
        channel_id,
        rule="hanchan",
        players_count=4,
        scores_str="@player1:25000,@player2:15000,@player3:-10000,@player4:-30000",
        interaction=mock_interaction,
        service="tenhou",
    )
    assert success is True
    expected_message = "ゲーム結果を記録しました。\n<@111111111111111111>: 25000 (1着), <@222222222222222222>: 15000 (2着), <@333333333333333333>: -10000 (3着), <@444444444444444444>: -30000 (4着)"
    assert message == expected_message
    assert len(current_gamesets[guild_id][channel_id]["games"]) == 1
    assert current_gamesets[guild_id][channel_id]["games"][0]["service"] == "tenhou"
    assert current_gamesets[guild_id][channel_id]["members"]["player1"] == 25000
    assert current_gamesets[guild_id][channel_id]["members"]["player2"] == 15000
    assert current_gamesets[guild_id][channel_id]["members"]["player3"] == -10000
    assert current_gamesets[guild_id][channel_id]["members"]["player4"] == -30000

    # 別のゲームを追加 (service指定なし、デフォルトjantama)
    success, message = await _record_game_logic(
        guild_id,
        channel_id,
        rule="tonpu",
        players_count=4,
        scores_str="@player1:10000,@player2:0,@player3:-5000,@player4:-5000",
        interaction=mock_interaction,
        service="jantama",
    )
    assert success is True
    expected_message = "ゲーム結果を記録しました。\n<@111111111111111111>: 10000 (1着), <@222222222222222222>: 0 (2着), <@333333333333333333>: -5000 (3着), <@444444444444444444>: -5000 (4着)"
    assert message == expected_message
    assert len(current_gamesets[guild_id][channel_id]["games"]) == 2
    assert current_gamesets[guild_id][channel_id]["games"][1]["service"] == "jantama"
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
        interaction=mock_interaction,
        service="jantama",
    )
    assert success is True
    expected_message = "ゲーム結果を記録しました。\n<@AAAAAAAAAAAAAAA>: 30000 (1着), <@BBBBBBBBBBBBBBB>: 0 (2着), <@CCCCCCCCCCCCCCC>: -30000 (3着)"
    assert message == expected_message
    assert len(current_gamesets[guild_id][channel_id]["games"]) == 3
    assert current_gamesets[guild_id][channel_id]["games"][2]["service"] == "jantama"
    assert current_gamesets[guild_id][channel_id]["members"]["playerA"] == 30000
    assert current_gamesets[guild_id][channel_id]["members"]["playerB"] == 0
    assert current_gamesets[guild_id][channel_id]["members"]["playerC"] == -30000


@pytest.mark.asyncio
async def test_record_game_logic_validation_errors(setup_teardown):
    from app.main import _record_game_logic, _start_gameset_logic

    guild_id = "123"
    channel_id = "456"
    mock_interaction = setup_teardown

    # ゲームセットが開始されていない場合
    success, message = await _record_game_logic(
        guild_id,
        channel_id,
        rule="hanchan",
        players_count=4,
        scores_str="@p1:0,@p2:0,@p3:0,@p4:0",
        interaction=mock_interaction,
        service="jantama",
    )
    assert success is False
    assert (
        message
        == "このチャンネルで進行中のゲームセットがありません。`/mj_start` で開始してください。"
    )

    await _start_gameset_logic(guild_id, channel_id, mock_interaction)

    # スコアの数が不足 (ヨンマで3人)
    success, message = await _record_game_logic(
        guild_id,
        channel_id,
        rule="hanchan",
        players_count=4,
        scores_str="@p1:0,@p2:0,@p3:0",
        interaction=mock_interaction,
        service="jantama",
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
        interaction=mock_interaction,
        service="jantama",
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
        interaction=mock_interaction,
        service="jantama",
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
        interaction=mock_interaction,
        service="jantama",
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
        interaction=mock_interaction,
        service="jantama",
    )
    assert success is False
    assert (
        message
        == "プレイヤー名 'p1' が重複しています。異なるプレイヤー名を入力してください。"
    )


@pytest.mark.asyncio
async def test_end_gameset_logic(setup_teardown):
    from app.main import (_end_gameset_logic, _record_game_logic,
                          _start_gameset_logic, current_gamesets)

    guild_id = "123"
    channel_id = "456"
    mock_interaction = setup_teardown

    # ゲームセットが開始されていない場合
    success, message = await _end_gameset_logic(
        guild_id, channel_id, interaction=mock_interaction
    )
    assert success is False
    assert message == "このチャンネルで進行中のゲームセットがありません。"

    # ゲームセットを開始
    await _start_gameset_logic(guild_id, channel_id, mock_interaction)

    # ゲームを記録
    await _record_game_logic(
        guild_id,
        channel_id,
        rule="hanchan",
        players_count=4,
        scores_str="@player1:25000,@player2:15000,@player3:-10000,@player4:-30000",
        interaction=mock_interaction,
        service="jantama",
    )

    await _record_game_logic(
        guild_id,
        channel_id,
        rule="tonpu",
        players_count=4,
        scores_str="@player1:10000,@player2:0,@player3:-5000,@player4:-5000",
        interaction=mock_interaction,
        service="tenhou",
    )

    # ゲームセットを終了
    success, message = await _end_gameset_logic(
        guild_id, channel_id, interaction=mock_interaction
    )
    assert success is True
    expected_message = (
        "## 麻雀ゲームセット結果\n"
        "- <@111111111111111111>: 35000\n"
        "- <@222222222222222222>: 15000\n"
        "- <@333333333333333333>: -15000\n"
        "- <@444444444444444444>: -35000\n"
    )
    assert message == expected_message
    assert current_gamesets[guild_id][channel_id]["status"] == "inactive"

    # 記録されたゲームがない場合
    current_gamesets[guild_id][channel_id] = {
        "status": "active",
        "games": [],
        "members": {},
    }
    success, message = await _end_gameset_logic(
        guild_id, channel_id, interaction=mock_interaction
    )
    assert success is True
    assert message == "ゲームセットを閉じました。記録されたゲームはありませんでした。"
    assert current_gamesets[guild_id][channel_id]["status"] == "inactive"
    assert current_gamesets[guild_id][channel_id]["games"] == []
    assert current_gamesets[guild_id][channel_id]["members"] == {}
