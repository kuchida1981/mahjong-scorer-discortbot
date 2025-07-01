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

    with patch("app.main.DATA_FILE", TEST_DATA_FILE):
        with patch("app.main.current_gamesets", {}):
            mock_interaction = AsyncMock()
            mock_guild = AsyncMock()
            mock_interaction.guild = mock_guild

            # モックメンバーのセットアップ
            players = [
                ("player1", "<@111111111111111111>"),
                ("player2", "<@222222222222222222>"),
                ("player3", "<@333333333333333333>"),
                ("player4", "<@444444444444444444>"),
                ("playerA", "<@AAAAAAAAAAAAAAA>"),
                ("playerB", "<@BBBBBBBBBBBBBBB>"),
                ("playerC", "<@CCCCCCCCCCCCCCC>"),
            ]
            mock_members = []
            for name, mention in players:
                member = AsyncMock()
                member.nick = name
                member.name = name
                member.mention = mention
                mock_members.append(member)
            mock_guild.members = mock_members

            yield mock_interaction

            app_main = importlib.import_module("app.main")
            app_main.current_gamesets.clear()

    if os.path.exists(TEST_DATA_FILE):
        os.remove(TEST_DATA_FILE)


@pytest.mark.asyncio
async def test_start_gameset_logic(setup_teardown):
    from app.main import _start_gameset_logic, current_gamesets

    guild_id = "123"
    channel_id = "456"
    mock_interaction = setup_teardown

    # 新規ゲームセット開始
    success, message = await _start_gameset_logic(
        guild_id, channel_id, mock_interaction
    )
    assert success is True
    assert (
        message
        == "麻雀のスコア集計を開始します。`/mj_member` で参加メンバーを登録し、`/mj_record` でゲーム結果を入力してください。"
    )
    assert current_gamesets[guild_id][channel_id]["status"] == "active"
    assert "registered_members" in current_gamesets[guild_id][channel_id]

    # 既存ゲームセットがある場合 (はい)
    with patch("app.main.ConfirmStartGamesetView", autospec=True) as MockView:
        mock_view_instance = MockView.return_value
        mock_view_instance.value = True
        mock_view_instance.wait = AsyncMock()
        success, message = await _start_gameset_logic(
            guild_id, channel_id, mock_interaction
        )
        assert success is True
        assert "麻雀のスコア集計を開始します" in message

    # 既存ゲームセットがある場合 (いいえ)
    with patch("app.main.ConfirmStartGamesetView", autospec=True) as MockView:
        mock_view_instance = MockView.return_value
        mock_view_instance.value = False
        mock_view_instance.wait = AsyncMock()
        success, message = await _start_gameset_logic(
            guild_id, channel_id, mock_interaction
        )
        assert success is False
        assert message == "新しいゲームセットの開始をキャンセルしました。"


@pytest.mark.asyncio
async def test_add_member_logic(setup_teardown):
    from app.main import (_add_member_logic, _start_gameset_logic,
                          current_gamesets)

    guild_id = "123"
    channel_id = "456"
    mock_interaction = setup_teardown

    # ゲームセット未開始
    success, message = await _add_member_logic(guild_id, channel_id, "player1")
    assert success is False
    assert "進行中のゲームセットがありません" in message

    await _start_gameset_logic(guild_id, channel_id, mock_interaction)

    # メンバー追加成功
    success, message = await _add_member_logic(guild_id, channel_id, "player1")
    assert success is True
    assert message == "メンバー 'player1' を登録しました。"
    assert "player1" in current_gamesets[guild_id][channel_id]["registered_members"]

    # メンバー重複
    success, message = await _add_member_logic(guild_id, channel_id, "player1")
    assert success is False
    assert message == "メンバー 'player1' はすでに登録されています。"


@pytest.mark.asyncio
async def test_list_members_logic(setup_teardown):
    from app.main import (_add_member_logic, _list_members_logic,
                          _start_gameset_logic)

    guild_id = "123"
    channel_id = "456"
    mock_interaction = setup_teardown

    await _start_gameset_logic(guild_id, channel_id, mock_interaction)

    # メンバーなし
    success, message = await _list_members_logic(guild_id, channel_id)
    assert success is True
    assert message == "現在登録されているメンバーはいません。"

    # メンバーあり
    await _add_member_logic(guild_id, channel_id, "player1")
    await _add_member_logic(guild_id, channel_id, "player2")
    success, message = await _list_members_logic(guild_id, channel_id)
    assert success is True
    assert message == "登録済みメンバー:\n- player1\n- player2"


@pytest.mark.asyncio
async def test_record_game_logic_success(setup_teardown):
    from app.main import _record_game_logic, current_gamesets

    guild_id = "123"
    channel_id = "456"
    mock_interaction = setup_teardown
    current_gamesets[guild_id] = {
        channel_id: {
            "status": "active",
            "games": [],
            "members": {},
            "registered_members": ["player1", "player2", "player3", "player4"],
        }
    }

    # 4人麻雀
    scores = {"player1": 25000, "player2": 15000, "player3": -10000, "player4": -30000}
    success, message = await _record_game_logic(
        guild_id,
        channel_id,
        "hanchan",
        4,
        scores,
        mock_interaction,
        "tenhou",
    )
    assert success is True
    assert "ゲーム結果を記録しました" in message
    assert current_gamesets[guild_id][channel_id]["members"]["player1"] == 25000


@pytest.mark.asyncio
async def test_record_game_logic_validation_errors(setup_teardown):
    from app.main import _record_game_logic, current_gamesets

    guild_id = "123"
    channel_id = "456"
    mock_interaction = setup_teardown

    # ゲームセット未開始
    success, message = await _record_game_logic(
        guild_id, channel_id, "hanchan", 4, {}, mock_interaction, "jantama"
    )
    assert success is False
    assert "進行中のゲームセットがありません" in message

    # ゲームセット開始
    current_gamesets[guild_id] = {
        channel_id: {"status": "active", "games": [], "members": {}}
    }

    # ゼロサムでない
    scores = {"player1": 10000, "player2": 0, "player3": 0, "player4": 0}
    success, message = await _record_game_logic(
        guild_id, channel_id, "hanchan", 4, scores, mock_interaction, "jantama"
    )
    assert success is False
    assert "スコアの合計が0になりません" in message


@pytest.mark.asyncio
async def test_mj_record_command(setup_teardown):
    import unittest

    from app.main import current_gamesets, mj_record

    guild_id = "123"
    channel_id = "456"
    mock_interaction = setup_teardown
    mock_interaction.guild_id = guild_id
    mock_interaction.channel_id = channel_id

    # ゲームセット未開始
    await mj_record.callback(
        mock_interaction, service="jantama", rule="hanchan", players=4
    )
    mock_interaction.response.send_message.assert_called_with(
        "このチャンネルで進行中のゲームセットがありません。`/mj_start` で開始してください。",
        ephemeral=True,
    )
    mock_interaction.response.send_message.reset_mock()

    # メンバー不足
    current_gamesets[guild_id] = {
        channel_id: {
            "status": "active",
            "registered_members": ["p1", "p2"],
        }
    }
    await mj_record.callback(
        mock_interaction, service="jantama", rule="hanchan", players=4
    )
    mock_interaction.response.send_message.assert_called_with(
        "登録されているメンバーが4人未満です。`/mj_member` でメンバーを登録してください。",
        ephemeral=True,
    )
    mock_interaction.response.send_message.reset_mock()

    # 正常系 (View表示)
    current_gamesets[guild_id][channel_id]["registered_members"] = [
        "p1",
        "p2",
        "p3",
        "p4",
    ]
    with patch("app.main.PlayerSelectView", autospec=True):
        await mj_record.callback(
            mock_interaction, service="jantama", rule="hanchan", players=4
        )
        mock_interaction.response.send_message.assert_called_with(
            "ゲームに参加したプレイヤーを選択してください:",
            view=unittest.mock.ANY,
            ephemeral=True,
        )


@pytest.mark.asyncio
async def test_end_gameset_logic(setup_teardown):
    from app.main import _end_gameset_logic, current_gamesets

    guild_id = "123"
    channel_id = "456"
    mock_interaction = setup_teardown

    # ゲームセット未開始
    success, message = await _end_gameset_logic(guild_id, channel_id, mock_interaction)
    assert success is False
    assert message == "このチャンネルで進行中のゲームセットがありません。"

    # ゲーム記録なし
    current_gamesets[guild_id] = {channel_id: {"status": "active", "members": {}}}
    success, message = await _end_gameset_logic(guild_id, channel_id, mock_interaction)
    assert success is True
    assert message == "ゲームセットを閉じました。記録されたゲームはありませんでした。"

    # ゲーム記録あり
    current_gamesets[guild_id][channel_id] = {
        "status": "active",
        "members": {"player1": 35000, "player2": -35000},
    }
    with patch("os.rename"), patch("app.main.save_gamesets"):
        success, message = await _end_gameset_logic(
            guild_id, channel_id, mock_interaction
        )
    assert success is True
    assert "麻雀ゲームセット結果" in message
    assert current_gamesets[guild_id][channel_id]["status"] == "inactive"
