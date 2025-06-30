import json
import os
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import discord
from discord.ext import commands
from discord.ui import Button, View

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
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")  # pragma: no cover
    print("------")  # pragma: no cover
    # 起動時にスラッシュコマンドを同期
    await bot.tree.sync()  # pragma: no cover
    print("Slash commands synced.")  # pragma: no cover


# ゲームセットのデータをロードする関数
def load_gamesets() -> Dict[str, Any]:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


# ゲームセットのデータを保存する関数
def save_gamesets(gamesets: Dict[str, Any]) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(gamesets, f, ensure_ascii=False, indent=4)


# プレイヤー名からDiscordのメンション文字列を取得するヘルパー関数
async def get_mention_from_player_name(
    interaction: discord.Interaction, player_name: str
) -> str:
    """プレイヤー名からDiscordのメンション文字列を取得する"""
    if interaction.guild:
        # ニックネームまたはユーザー名でメンバーを検索
        for member in interaction.guild.members:
            if member.nick == player_name or member.name == player_name:
                return member.mention
    return player_name  # 見つからない場合は元のプレイヤー名を返す


# 現在進行中のゲームセットを管理する辞書
# { guild_id: { channel_id: { "status": "active", "games": [], "members": {} } } }
current_gamesets = load_gamesets()


class ConfirmStartGamesetView(View):  # pragma: no cover
    def __init__(self, guild_id: str, channel_id: str):
        super().__init__(timeout=60)  # 60秒でタイムアウト
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.value: Optional[bool] = None  # ユーザーの選択 (True: はい, False: いいえ)

    @discord.ui.button(label="はい", style=discord.ButtonStyle.green)
    async def confirm(
        self, interaction: discord.Interaction, button: Button
    ):  # pragma: no cover
        self.value = True
        self.stop()
        await interaction.response.edit_message(
            content="既存のゲームセットを破棄し、新しいゲームセットを開始します。",
            view=None,
        )

    @discord.ui.button(label="いいえ", style=discord.ButtonStyle.red)
    async def cancel(
        self, interaction: discord.Interaction, button: Button
    ):  # pragma: no cover
        self.value = False
        self.stop()
        await interaction.response.edit_message(
            content="新しいゲームセットの開始をキャンセルしました。", view=None
        )


async def _start_gameset_logic(
    guild_id: str, channel_id: str, interaction: discord.Interaction
) -> Tuple[bool, str]:
    """ゲームセット開始のロジック"""
    if guild_id not in current_gamesets:
        current_gamesets[guild_id] = {}

    if (
        channel_id in current_gamesets[guild_id]
        and current_gamesets[guild_id][channel_id]["status"] == "active"
    ):
        # 確認ダイアログを表示
        view = ConfirmStartGamesetView(guild_id, channel_id)
        await interaction.response.send_message(
            "すでにこのチャンネルでゲームセットが進行中です。現在のゲームセットを破棄して、新しいゲームセットを開始しますか？",
            view=view,
            ephemeral=True,
        )
        await view.wait()  # ユーザーの応答を待つ

        if view.value is True:
            # 既存のゲームセットを破棄
            current_gamesets[guild_id][channel_id] = {
                "status": "inactive",
                "games": [],
                "members": {},
            }
            save_gamesets(current_gamesets)
            # 新しいゲームセットを開始
            current_gamesets[guild_id][channel_id] = {
                "status": "active",
                "games": [],
                "members": {},
            }
            save_gamesets(current_gamesets)
            return (
                True,
                "既存のゲームセットを破棄し、新しい麻雀のスコア集計を開始します。`/record_game` でゲーム結果を入力してください。",
            )
        else:
            return False, "新しいゲームセットの開始をキャンセルしました。"

    current_gamesets[guild_id][channel_id] = {
        "status": "active",
        "games": [],
        "members": {},
    }
    save_gamesets(current_gamesets)
    return (
        True,
        "麻雀のスコア集計を開始します。`/record_game` でゲーム結果を入力してください。",
    )


async def _record_game_logic(
    guild_id: str,
    channel_id: str,
    rule: str,
    players_count: int,
    scores_str: str,
    interaction: discord.Interaction,
) -> Tuple[bool, str]:
    """ゲーム結果記録のロジック"""
    if (
        guild_id not in current_gamesets
        or channel_id not in current_gamesets[guild_id]
        or current_gamesets[guild_id][channel_id]["status"] != "active"
    ):
        return (
            False,
            "このチャンネルで進行中のゲームセットがありません。`/start_gameset` で開始してください。",
        )

    # ルールのバリデーション
    if rule not in ["tonpu", "hanchan"]:
        return (
            False,
            "ルールは 'tonpu' (東風戦) または 'hanchan' (半荘戦) で指定してください。",
        )

    # 人数のバリデーション
    if players_count not in [3, 4]:
        return False, "参加人数は 3 (サンマ) または 4 (4人) で指定してください。"

    expected_players_count = players_count

    parsed_scores = {}
    total_score = 0

    score_entries = [s.strip() for s in scores_str.split(",")]

    if len(score_entries) != expected_players_count:
        return (
            False,
            f"{expected_players_count}人分のスコアを入力してください。現在 {len(score_entries)}人分のスコアが入力されています。",
        )

    player_names = []
    for entry in score_entries:
        try:
            name, score_str_val = entry.split(":")
            player_name = name.strip().lstrip("@")  # @を削除
            score = int(score_str_val)

            if player_name in player_names:
                return (
                    False,
                    f"プレイヤー名 '{player_name}' が重複しています。異なるプレイヤー名を入力してください。",
                )
            player_names.append(player_name)
            parsed_scores[player_name] = score
            total_score += score
        except ValueError:  # pragma: no cover
            return (
                False,
                "スコアの形式が正しくありません。`名前:スコア` の形式で入力してください (例: `@player1:25000`)。",
            )
        except IndexError:  # pragma: no cover
            return (
                False,
                "スコアの形式が正しくありません。`名前:スコア` の形式で入力してください (例: `@player1:25000`)。",
            )

    # ゼロサムチェック
    if total_score != 0:
        return (
            False,
            f"スコアの合計が0になりません。現在の合計: {total_score}。再入力してください。",
        )

    game_data = {"rule": rule, "players_count": players_count, "scores": parsed_scores}
    current_gamesets[guild_id][channel_id]["games"].append(game_data)

    # メンバーのスコアを更新
    for player_name, score in parsed_scores.items():
        if player_name not in current_gamesets[guild_id][channel_id]["members"]:
            current_gamesets[guild_id][channel_id]["members"][player_name] = 0
        current_gamesets[guild_id][channel_id]["members"][player_name] += score

    save_gamesets(current_gamesets)

    # 順位を計算し、メッセージを生成
    sorted_game_scores = sorted(
        parsed_scores.items(), key=lambda item: item[1], reverse=True
    )
    result_parts = []
    for i, (player, score) in enumerate(sorted_game_scores):
        rank = i + 1
        mention = await get_mention_from_player_name(interaction, player)
        result_parts.append(f"{mention}: {score} ({rank}着)")

    return True, "ゲーム結果を記録しました。\n" + ", ".join(result_parts)


async def _current_scores_logic(
    guild_id: str, channel_id: str, interaction: discord.Interaction
) -> Tuple[bool, str]:
    """現在のトータルスコアと順位を出力するロジック"""
    if (
        guild_id not in current_gamesets
        or channel_id not in current_gamesets[guild_id]
        or current_gamesets[guild_id][channel_id]["status"] != "active"
    ):
        return (
            False,
            "このチャンネルで進行中のゲームセットがありません。`/start_gameset` で開始してください。",
        )

    gameset_data = current_gamesets[guild_id][channel_id]
    total_scores = gameset_data["members"]

    if not total_scores:
        return False, "まだゲームが記録されていません。"

    # スコアを降順にソート
    sorted_scores = sorted(total_scores.items(), key=lambda item: item[1], reverse=True)

    result_message = "## 現在のトータルスコア\n"
    for i, (player, score) in enumerate(sorted_scores):
        rank = i + 1
        mention = await get_mention_from_player_name(interaction, player)
        result_message += f"- {mention}: {score} ({rank}位)\n"

    return True, result_message


async def _end_gameset_logic(
    guild_id: str, channel_id: str, interaction: discord.Interaction
) -> Tuple[bool, str]:
    """ゲームセット完了のロジック"""
    if (
        guild_id not in current_gamesets
        or channel_id not in current_gamesets[guild_id]
        or current_gamesets[guild_id][channel_id]["status"] != "active"
    ):
        return False, "このチャンネルで進行中のゲームセットがありません。"

    gameset_data = current_gamesets[guild_id][channel_id]
    total_scores = gameset_data["members"]

    # ゲーム記録がない場合、メッセージを返さずにゲームセットを閉じる
    if not total_scores:
        current_gamesets[guild_id][channel_id]["status"] = "inactive"
        save_gamesets(current_gamesets)
        # current_gamesetsもクリアする
        current_gamesets[guild_id][channel_id] = {
            "status": "inactive",
            "games": [],
            "members": {},
        }
        return True, "ゲームセットを閉じました。記録されたゲームはありませんでした。"

    # スコアを降順にソート
    sorted_scores = sorted(total_scores.items(), key=lambda item: item[1], reverse=True)

    result_message = "## 麻雀ゲームセット結果\n"
    for player, score in sorted_scores:
        mention = await get_mention_from_player_name(interaction, player)
        result_message += f"- {mention}: {score}\n"

    # ゲームセットを非アクティブにする
    current_gamesets[guild_id][channel_id]["status"] = "inactive"
    save_gamesets(current_gamesets)

    # ファイルをリネーム
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    new_file_name = f"gamesets.{timestamp}.json"
    if os.path.exists(DATA_FILE):
        os.rename(DATA_FILE, new_file_name)
        # リネーム後、gamesets.jsonを空にする
        save_gamesets({})
        # current_gamesetsもクリアする
        current_gamesets[guild_id][channel_id] = {
            "status": "inactive",
            "games": [],
            "members": {},
        }

    return True, result_message


# ゲームセット開始コマンド
@bot.tree.command(
    name="start_gameset", description="麻雀のスコア集計を開始します。"
)  # pragma: no cover
async def start_gameset(interaction: discord.Interaction):  # pragma: no cover
    guild_id = str(interaction.guild_id)  # pragma: no cover
    channel_id = str(interaction.channel_id)  # pragma: no cover
    success, message = await _start_gameset_logic(
        guild_id, channel_id, interaction
    )  # pragma: no cover
    await interaction.response.send_message(
        message, ephemeral=not success
    )  # pragma: no cover


# ゲーム結果記録コマンド
@bot.tree.command(
    name="record_game", description="1ゲームの麻雀結果を記録します。"
)  # pragma: no cover
@discord.app_commands.describe(  # pragma: no cover
    rule="ゲームのルール (東風戦:tonpu / 半荘戦:hanchan)",  # pragma: no cover
    players="参加人数 (3:サンマ / 4:4人)",  # pragma: no cover
    scores="プレイヤー名とスコアのペアをカンマ区切りで入力してください (例: @player1:25000, @player2:15000, @player3:-10000, @player4:-30000)",  # pragma: no cover
)
async def record_game(  # pragma: no cover
    interaction: discord.Interaction,
    rule: str,
    players: int,
    scores: str,  # pragma: no cover
):  # pragma: no cover
    guild_id = str(interaction.guild_id)  # pragma: no cover
    channel_id = str(interaction.channel_id)  # pragma: no cover
    success, message = await _record_game_logic(
        guild_id, channel_id, rule, players, scores, interaction
    )  # pragma: no cover
    await interaction.response.send_message(
        message, ephemeral=not success
    )  # pragma: no cover


# ゲームセット完了コマンド
@bot.tree.command(  # pragma: no cover
    name="end_gameset",
    description="麻雀のスコア集計を完了し、結果を出力します。",  # pragma: no cover
)
async def end_gameset(interaction: discord.Interaction):  # pragma: no cover
    guild_id = str(interaction.guild_id)  # pragma: no cover
    channel_id = str(interaction.channel_id)  # pragma: no cover
    success, message = await _end_gameset_logic(
        guild_id, channel_id, interaction
    )  # pragma: no cover
    await interaction.response.send_message(
        message, ephemeral=not success
    )  # pragma: no cover


# 現在のスコア表示コマンド
@bot.tree.command(
    name="current_scores", description="現在のトータルスコアと順位を表示します。"
)  # pragma: no cover
async def current_scores(interaction: discord.Interaction):  # pragma: no cover
    guild_id = str(interaction.guild_id)  # pragma: no cover
    channel_id = str(interaction.channel_id)  # pragma: no cover
    success, message = await _current_scores_logic(
        guild_id, channel_id, interaction
    )  # pragma: no cover
    await interaction.response.send_message(
        message, ephemeral=not success
    )  # pragma: no cover


# ボットの実行
if DISCORD_BOT_TOKEN:  # pragma: no cover
    bot.run(DISCORD_BOT_TOKEN)  # pragma: no cover
else:  # pragma: no cover
    print("DISCORD_BOT_TOKEN 環境変数が設定されていません。")  # pragma: no cover
