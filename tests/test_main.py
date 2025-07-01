import importlib
import os
from unittest.mock import AsyncMock, patch

import pytest
from discord import Member

# テスト用にDATA_FILEを上書き
TEST_DATA_FILE = "test_gamesets.json"


@pytest.fixture
def mock_member() -> Member:
    member = AsyncMock(spec=Member)
    member.id = 1234567890
    member.display_name = "test_user"
    return member


@pytest.fixture(autouse=True)
def setup_teardown(mock_member: Member):
    # テスト開始前にテスト用ファイルを削除
    if os.path.exists(TEST_DATA_FILE):
        os.remove(TEST_DATA_FILE)

    with patch("app.main.DATA_FILE", TEST_DATA_FILE):
        with patch("app.main.current_gamesets", {}):
            mock_interaction = AsyncMock()
            mock_guild = AsyncMock()
            mock_interaction.guild = mock_guild
            mock_guild.fetch_member.return_value = mock_member

            # モックメンバーのセットアップ
            players = [
                (1, "player1", "<@1>"),
                (2, "player2", "<@2>"),
                (3, "player3", "<@3>"),
                (4, "player4", "<@4>"),
            ]
            mock_members = []
            for id, name, mention in players:
                member = AsyncMock(spec=Member)
                member.id = id
                member.display_name = name
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

    success, message = await _start_gameset_logic(
        guild_id, channel_id, mock_interaction
    )
    assert success is True
    assert "麻雀のスコア集計を開始します" in message
    assert current_gamesets[guild_id][channel_id]["status"] == "active"


@pytest.mark.asyncio
async def test_add_member_logic(setup_teardown, mock_member: Member):
    from app.main import (_add_member_logic, _start_gameset_logic,
                          current_gamesets)

    guild_id = "123"
    channel_id = "456"
    mock_interaction = setup_teardown

    await _start_gameset_logic(guild_id, channel_id, mock_interaction)

    success, message = await _add_member_logic(guild_id, channel_id, mock_member)
    assert success is True
    assert message == f"メンバー '{mock_member.display_name}' を登録しました。"
    assert {
        "id": mock_member.id,
        "display_name": mock_member.display_name,
    } in current_gamesets[guild_id][channel_id]["registered_members"]

    success, message = await _add_member_logic(guild_id, channel_id, mock_member)
    assert success is False
    assert (
        message == f"メンバー '{mock_member.display_name}' はすでに登録されています。"
    )


@pytest.mark.asyncio
async def test_list_members_logic(setup_teardown, mock_member: Member):
    from app.main import (_add_member_logic, _list_members_logic,
                          _start_gameset_logic)

    guild_id = "123"
    channel_id = "456"
    mock_interaction = setup_teardown

    await _start_gameset_logic(guild_id, channel_id, mock_interaction)

    success, message = await _list_members_logic(guild_id, channel_id)
    assert success is True
    assert message == "現在登録されているメンバーはいません。"

    await _add_member_logic(guild_id, channel_id, mock_member)
    success, message = await _list_members_logic(guild_id, channel_id)
    assert success is True
    assert message == f"登録済みメンバー:\n- {mock_member.display_name}"


@pytest.mark.asyncio
async def test_record_game_logic_success(setup_teardown):
    from app.main import _record_game_logic, current_gamesets

    guild_id = "123"
    channel_id = "456"
    mock_interaction = setup_teardown
    selected_players = [
        {"id": 1, "display_name": "player1"},
        {"id": 2, "display_name": "player2"},
        {"id": 3, "display_name": "player3"},
        {"id": 4, "display_name": "player4"},
    ]
    current_gamesets[guild_id] = {
        channel_id: {
            "status": "active",
            "games": [],
            "members": {},
            "registered_members": selected_players,
        }
    }

    scores = {
        "player1": 25000,
        "player2": 15000,
        "player3": -10000,
        "player4": -30000,
    }
    success, message = await _record_game_logic(
        guild_id,
        channel_id,
        "hanchan",
        4,
        scores,
        mock_interaction,
        "tenhou",
        selected_players,
    )
    assert success is True
    assert "ゲーム結果を記録しました" in message
    assert current_gamesets[guild_id][channel_id]["members"]["player1"] == 25000


@pytest.mark.asyncio
async def test_end_gameset_logic(setup_teardown):
    from app.main import _end_gameset_logic, current_gamesets

    guild_id = "123"
    channel_id = "456"
    mock_interaction = setup_teardown

    current_gamesets[guild_id] = {
        channel_id: {
            "status": "active",
            "members": {"player1": 35000, "player2": -35000},
            "registered_members": [
                {"id": 1, "display_name": "player1"},
                {"id": 2, "display_name": "player2"},
            ],
        }
    }
    with patch("os.rename"), patch("app.main.save_gamesets"):
        success, message = await _end_gameset_logic(
            guild_id, channel_id, mock_interaction
        )
    assert success is True
    assert "麻雀ゲームセット結果" in message
