import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import discord
from discord.ext import commands
from discord.ui import Button, Modal, Select, TextInput, View

# 環境変数からDiscordボットのトークンを取得
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# プレフィックスなしでスラッシュコマンドを使用
intents = discord.Intents.default()
intents.message_content = True  # メッセージの内容を読み取るためのインテントを有効にする
intents.members = True  # メンバー情報を取得するためのインテントを有効にする
bot = commands.Bot(command_prefix=commands.when_mentioned_or("!"), intents=intents)

# データの保存先ファイル
DATA_FILE = "gamesets.json"


# 起動時の処理
@bot.event
async def on_ready():  # pragma: no cover
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")
    # 起動時にスラッシュコマンドを同期
    await bot.tree.sync()
    print("Slash commands synced.")


# ゲームセットのデータをロードする関数
def load_gamesets() -> Dict[str, Any]:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


# ゲームセットのデータを保存する関数
def save_gamesets(gamesets: Dict[str, Any]) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(gamesets, f, ensure_ascii=False, indent=4)


# プレイヤー名からDiscordのメンション文字列を取得するヘルパー関数
async def get_mention_from_player_id(
    interaction: discord.Interaction, player_id: int
) -> str:
    """プレイヤーIDからDiscordのメンション文字列を取得する"""
    if interaction.guild:
        member = await interaction.guild.fetch_member(player_id)
        if member:
            return member.mention
    return f"<@{player_id}>"  # 見つからない場合はIDを返す


# 現在進行中のゲームセットを管理する辞書
# { guild_id: { channel_id: { "status": "active", "games": [], "members": {}, "registered_members": [] } } }
current_gamesets = load_gamesets()


class ConfirmStartGamesetView(View):  # pragma: no cover
    def __init__(self, guild_id: str, channel_id: str):
        super().__init__(timeout=60)  # 60秒でタイムアウト
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.value: Optional[bool] = None  # ユーザーの選択 (True: はい, False: いいえ)

    @discord.ui.button(label="はい", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        self.value = True
        self.stop()
        await interaction.response.edit_message(
            content="既存のゲームセットを破棄し、新しいゲームセットを開始します。",
            view=None,
        )

    @discord.ui.button(label="いいえ", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        self.value = False
        self.stop()
        await interaction.response.edit_message(
            content="新しいゲームセットの開始をキャンセルしました。", view=None
        )


class ScoreInputModal(Modal, title="スコア入力"):
    def __init__(self, players: List[str]):
        super().__init__()
        self.players = players
        for player in players:
            self.add_item(
                TextInput(
                    label=f"{player} のスコア",
                    placeholder="点数を入力してください",
                    required=True,
                )
            )

    async def on_submit(self, interaction: discord.Interaction):
        self.scores = {
            player: int(item.value)
            for player, item in zip(self.players, self.children)
            if isinstance(item, TextInput)
        }
        await interaction.response.defer()  # 後続処理に時間を要するため
        self.stop()


class PlayerSelectView(View):
    def __init__(
        self,
        registered_members: List[Dict[str, Any]],
        players_count: int,
        rule: str,
        service: str,
    ):
        super().__init__(timeout=180)
        self.registered_members = registered_members
        self.players_count = players_count
        self.rule = rule
        self.service = service
        self.selected_players: List[Dict[str, Any]] = []

        self.select: Select = Select(
            placeholder="プレイヤーを選択してください",
            min_values=players_count,
            max_values=players_count,
            options=[
                discord.SelectOption(
                    label=member["display_name"], value=str(member["id"])
                )
                for member in registered_members
            ],
        )
        self.select.callback = self.select_callback  # type: ignore
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        selected_ids = [int(v) for v in self.select.values]
        self.selected_players = [
            member for member in self.registered_members if member["id"] in selected_ids
        ]
        player_names = [p["display_name"] for p in self.selected_players]
        modal = ScoreInputModal(player_names)
        await interaction.response.send_modal(modal)
        await modal.wait()

        if hasattr(modal, "scores"):
            guild_id = str(interaction.guild_id)
            channel_id = str(interaction.channel_id)
            success, message = await _record_game_logic(
                guild_id,
                channel_id,
                self.rule,
                self.players_count,
                modal.scores,
                interaction,
                self.service,
                self.selected_players,
            )
            # on_submitでdefer()しているので、followup.sendを使う
            await interaction.followup.send(message, ephemeral=not success)
        self.stop()


async def _start_gameset_logic(
    guild_id: str, channel_id: str, interaction: discord.Interaction
) -> Tuple[bool, str]:
    """ゲームセット開始のロジック"""
    if guild_id not in current_gamesets:
        current_gamesets[guild_id] = {}

    if (
        channel_id in current_gamesets[guild_id]
        and current_gamesets[guild_id][channel_id].get("status") == "active"
    ):
        view = ConfirmStartGamesetView(guild_id, channel_id)
        await interaction.response.send_message(
            "すでにこのチャンネルでゲームセットが進行中です。現在のゲームセットを破棄して、新しいゲームセットを開始しますか？",
            view=view,
            ephemeral=True,
        )
        await view.wait()

        if view.value is not True:
            return False, "新しいゲームセットの開始をキャンセルしました。"

    current_gamesets[guild_id][channel_id] = {
        "status": "active",
        "games": [],
        "members": {},
        "registered_members": [],
    }
    save_gamesets(current_gamesets)
    return (
        True,
        "麻雀のスコア集計を開始します。`/mj_member` で参加メンバーを登録し、`/mj_record` でゲーム結果を入力してください。",
    )


async def _add_member_logic(
    guild_id: str, channel_id: str, member: discord.Member
) -> Tuple[bool, str]:
    """メンバー登録のロジック"""
    if (
        guild_id not in current_gamesets
        or channel_id not in current_gamesets[guild_id]
        or current_gamesets[guild_id][channel_id].get("status") != "active"
    ):
        return (
            False,
            "このチャンネルで進行中のゲームセットがありません。`/mj_start` で開始してください。",
        )

    gameset = current_gamesets[guild_id][channel_id]
    if "registered_members" not in gameset:
        gameset["registered_members"] = []

    if any(m["id"] == member.id for m in gameset["registered_members"]):
        return False, f"メンバー '{member.display_name}' はすでに登録されています。"

    gameset["registered_members"].append(
        {"id": member.id, "display_name": member.display_name}
    )
    save_gamesets(current_gamesets)
    return True, f"メンバー '{member.display_name}' を登録しました。"


async def _list_members_logic(guild_id: str, channel_id: str) -> Tuple[bool, str]:
    """メンバー一覧表示のロジック"""
    if (
        guild_id not in current_gamesets
        or channel_id not in current_gamesets[guild_id]
        or current_gamesets[guild_id][channel_id].get("status") != "active"
    ):
        return (
            False,
            "このチャンネルで進行中のゲームセットがありません。`/mj_start` で開始してください。",
        )

    registered_members = current_gamesets[guild_id][channel_id].get(
        "registered_members", []
    )
    if not registered_members:
        return True, "現在登録されているメンバーはいません。"

    member_list = [m["display_name"] for m in registered_members]
    return True, "登録済みメンバー:\n- " + "\n- ".join(member_list)


async def _record_game_logic(
    guild_id: str,
    channel_id: str,
    rule: str,
    players_count: int,
    parsed_scores: Dict[str, int],
    interaction: discord.Interaction,
    service: str,
    selected_players: List[Dict[str, Any]],
) -> Tuple[bool, str]:
    """ゲーム結果記録のロジック"""
    if (
        guild_id not in current_gamesets
        or channel_id not in current_gamesets[guild_id]
        or current_gamesets[guild_id][channel_id].get("status") != "active"
    ):
        return (
            False,
            "このチャンネルで進行中のゲームセットがありません。`/mj_start` で開始してください。",
        )

    total_score = sum(parsed_scores.values())
    if total_score != 0:
        return (
            False,
            f"スコアの合計が0になりません。現在の合計: {total_score}。再入力してください。",
        )

    game_data = {
        "rule": rule,
        "players_count": players_count,
        "scores": parsed_scores,
        "service": service,
    }
    current_gamesets[guild_id][channel_id]["games"].append(game_data)

    for player_name, score in parsed_scores.items():
        if player_name not in current_gamesets[guild_id][channel_id]["members"]:
            current_gamesets[guild_id][channel_id]["members"][player_name] = 0
        current_gamesets[guild_id][channel_id]["members"][player_name] += score

    save_gamesets(current_gamesets)

    sorted_game_scores = sorted(
        parsed_scores.items(), key=lambda item: item[1], reverse=True
    )
    result_parts = []
    for i, (player, score) in enumerate(sorted_game_scores):
        rank = i + 1
        # playerはdisplay_nameなので、IDに変換する必要がある
        player_id = None
        for p in selected_players:
            if p["display_name"] == player:
                player_id = p["id"]
                break
        if player_id:
            mention = await get_mention_from_player_id(interaction, player_id)
            result_parts.append(f"{mention}: {score} ({rank}着)")
        else:
            result_parts.append(f"{player}: {score} ({rank}着)")

    return True, "ゲーム結果を記録しました。\n" + ", ".join(result_parts)


async def _current_scores_logic(
    guild_id: str, channel_id: str, interaction: discord.Interaction
) -> Tuple[bool, str]:
    """現在のトータルスコアと順位を出力するロジック"""
    if (
        guild_id not in current_gamesets
        or channel_id not in current_gamesets[guild_id]
        or current_gamesets[guild_id][channel_id].get("status") != "active"
    ):
        return (
            False,
            "このチャンネルで進行中のゲームセットがありません。`/mj_start` で開始してください。",
        )

    gameset_data = current_gamesets[guild_id][channel_id]
    total_scores = gameset_data.get("members", {})

    if not total_scores:
        return False, "まだゲームが記録されていません。"

    sorted_scores = sorted(total_scores.items(), key=lambda item: item[1], reverse=True)

    result_message = "## 現在のトータルスコア\n"
    for i, (player, score) in enumerate(sorted_scores):
        rank = i + 1
        # playerはdisplay_nameなので、IDに変換する必要がある
        player_id = None
        # registered_membersから探す
        for m in gameset_data.get("registered_members", []):
            if m["display_name"] == player:
                player_id = m["id"]
                break
        if player_id:
            mention = await get_mention_from_player_id(interaction, player_id)
            result_message += f"- {mention}: {score} ({rank}位)\n"
        else:
            result_message += f"- {player}: {score} ({rank}位)\n"

    return True, result_message


async def _end_gameset_logic(
    guild_id: str, channel_id: str, interaction: discord.Interaction
) -> Tuple[bool, str]:
    """ゲームセット完了のロジック"""
    if (
        guild_id not in current_gamesets
        or channel_id not in current_gamesets[guild_id]
        or current_gamesets[guild_id][channel_id].get("status") != "active"
    ):
        return False, "このチャンネルで進行中のゲームセットがありません。"

    gameset_data = current_gamesets[guild_id][channel_id]
    total_scores = gameset_data.get("members", {})

    if not total_scores:
        current_gamesets[guild_id][channel_id]["status"] = "inactive"
        save_gamesets(current_gamesets)
        return True, "ゲームセットを閉じました。記録されたゲームはありませんでした。"

    sorted_scores = sorted(total_scores.items(), key=lambda item: item[1], reverse=True)

    result_message = "## 麻雀ゲームセット結果\n"
    for i, (player, score) in enumerate(sorted_scores):
        rank = i + 1
        # playerはdisplay_nameなので、IDに変換する必要がある
        player_id = None
        # registered_membersから探す
        for m in gameset_data.get("registered_members", []):
            if m["display_name"] == player:
                player_id = m["id"]
                break
        if player_id:
            mention = await get_mention_from_player_id(interaction, player_id)
            result_message += f"- {mention}: {score} ({rank}位)\n"
        else:
            result_message += f"- {player}: {score} ({rank}位)\n"

    current_gamesets[guild_id][channel_id]["status"] = "inactive"
    save_gamesets(current_gamesets)

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    new_file_name = f"gamesets.{timestamp}.json"
    if os.path.exists(DATA_FILE):
        os.rename(DATA_FILE, new_file_name)
        save_gamesets({})

    return True, result_message


@bot.tree.command(name="mj_start", description="麻雀のスコア集計を開始します。")
async def mj_start(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    channel_id = str(interaction.channel_id)
    success, message = await _start_gameset_logic(guild_id, channel_id, interaction)
    if not interaction.response.is_done():
        await interaction.response.send_message(message, ephemeral=not success)


@bot.tree.command(
    name="mj_member", description="ゲームセットに参加するメンバーを登録します。"
)
@discord.app_commands.describe(member="登録するメンバー")
async def mj_member(interaction: discord.Interaction, member: discord.Member):
    guild_id = str(interaction.guild_id)
    channel_id = str(interaction.channel_id)
    success, message = await _add_member_logic(guild_id, channel_id, member)
    await interaction.response.send_message(message, ephemeral=not success)


@bot.tree.command(
    name="mj_member_list", description="登録されているメンバーの一覧を表示します。"
)
async def mj_member_list(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    channel_id = str(interaction.channel_id)
    success, message = await _list_members_logic(guild_id, channel_id)
    await interaction.response.send_message(message, ephemeral=not success)


@bot.tree.command(name="mj_record", description="1ゲームの麻雀結果を記録します。")
@discord.app_commands.choices(  # type: ignore
    service=[
        discord.app_commands.Choice(name="雀魂", value="jantama"),
        discord.app_commands.Choice(name="天鳳", value="tenhou"),
    ],
    rule=[
        discord.app_commands.Choice(name="東風戦", value="tonpu"),
        discord.app_commands.Choice(name="半荘戦", value="hanchan"),
    ],
    players=[
        discord.app_commands.Choice(name="3人", value=3),
        discord.app_commands.Choice(name="4人", value=4),
    ],
)
@discord.app_commands.describe(
    service="麻雀サービスを選択してください",
    rule="ゲームのルールを選択してください",
    players="参加人数を選択してください",
)
async def mj_record(
    interaction: discord.Interaction, service: str, rule: str, players: int
):
    guild_id = str(interaction.guild_id)
    channel_id = str(interaction.channel_id)

    if (
        guild_id not in current_gamesets
        or channel_id not in current_gamesets[guild_id]
        or current_gamesets[guild_id][channel_id].get("status") != "active"
    ):
        await interaction.response.send_message(
            "このチャンネルで進行中のゲームセットがありません。`/mj_start` で開始してください。",
            ephemeral=True,
        )
        return

    registered_members = current_gamesets[guild_id][channel_id].get(
        "registered_members", []
    )
    if len(registered_members) < players:
        await interaction.response.send_message(
            f"登録されているメンバーが{players}人未満です。`/mj_member` でメンバーを登録してください。",
            ephemeral=True,
        )
        return

    view = PlayerSelectView(registered_members, players, rule, service)
    await interaction.response.send_message(
        "ゲームに参加したプレイヤーを選択してください:", view=view, ephemeral=True
    )


@bot.tree.command(
    name="mj_end", description="麻雀のスコア集計を完了し、結果を出力します。"
)
async def mj_end(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    channel_id = str(interaction.channel_id)
    success, message = await _end_gameset_logic(guild_id, channel_id, interaction)
    await interaction.response.send_message(message, ephemeral=not success)


@bot.tree.command(
    name="mj_scores", description="現在のトータルスコアと順位を表示します。"
)
async def mj_scores(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    channel_id = str(interaction.channel_id)
    success, message = await _current_scores_logic(guild_id, channel_id, interaction)
    await interaction.response.send_message(message, ephemeral=not success)


# ボットの実行
if __name__ == "__main__":  # pragma: no cover
    if DISCORD_BOT_TOKEN:
        bot.run(DISCORD_BOT_TOKEN)
    else:
        print("DISCORD_BOT_TOKEN 環境変数が設定されていません。")
