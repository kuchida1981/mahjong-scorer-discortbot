from typing import Optional

import discord
from discord.ext import commands
from discord.ui import Button, View

from app.core.gameset_manager import GamesetManager

# GamesetManagerのインスタンスを作成
gameset_manager = GamesetManager()


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


class ConfirmStartGamesetView(View):
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


# ゲームセット開始コマンド
@discord.app_commands.command(
    name="mj_start", description="麻雀のスコア集計を開始します。"
)
async def mj_start(interaction: discord.Interaction):  # type: ignore
    guild_id = str(interaction.guild_id)
    channel_id = str(interaction.channel_id)

    # 既存のゲームセットがあるか確認し、確認ダイアログを表示
    if (
        guild_id in gameset_manager.current_gamesets.root
        and channel_id in gameset_manager.current_gamesets[guild_id]
        and gameset_manager.current_gamesets[guild_id][channel_id].status == "active"
    ):
        view = ConfirmStartGamesetView(guild_id, channel_id)
        await interaction.response.send_message(
            "すでにこのチャンネルでゲームセットが進行中です。現在のゲームセットを破棄して、新しいゲームセットを開始しますか？",
            view=view,
            ephemeral=True,
        )
        await view.wait()  # ユーザーの応答を待つ

        if view.value is False:
            await interaction.followup.send(
                "新しいゲームセットの開始をキャンセルしました。", ephemeral=True
            )
            return

    success, message_prefix = gameset_manager.start_gameset(guild_id, channel_id)
    final_message = (
        f"{message_prefix} `/mj_record` でゲーム結果を入力してください。"
        if success
        else message_prefix
    )
    await interaction.response.send_message(final_message, ephemeral=not success)


# ゲーム結果記録コマンド
@discord.app_commands.command(
    name="mj_record", description="1ゲームの麻雀結果を記録します。"
)
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
    service="麻雀サービスを選択してください (デフォルト: 雀魂)",
    rule="ゲームのルールを選択してください",
    players="参加人数を選択してください",
    scores="プレイヤー名とスコアのペアをカンマ区切りで入力してください (例: @player1:25000, @player2:15000, @player3:-10000, @player4:-30000)",
)
async def mj_record(
    interaction: discord.Interaction,  # type: ignore
    service: str,
    rule: str,
    players: int,
    scores: str,
):
    guild_id = str(interaction.guild_id)
    channel_id = str(interaction.channel_id)

    success, message, sorted_scores = gameset_manager.record_game(
        guild_id,
        channel_id,
        rule,
        players,
        scores,
        service,
    )

    if success and sorted_scores:
        result_parts = []
        for i, (player, score) in enumerate(sorted_scores):
            rank = i + 1
            mention = await get_mention_from_player_name(interaction, player)
            result_parts.append(f"{mention}: {score} ({rank}着)")
        final_message = f"{message}\n" + ", ".join(result_parts)
    else:
        final_message = message

    await interaction.response.send_message(final_message, ephemeral=not success)


# 現在のスコア表示コマンド
@discord.app_commands.command(
    name="mj_scores", description="現在のトータルスコアと順位を表示します。"
)
async def mj_scores(interaction: discord.Interaction):  # type: ignore
    guild_id = str(interaction.guild_id)
    channel_id = str(interaction.channel_id)

    success, message, sorted_scores = gameset_manager.get_current_scores(
        guild_id, channel_id
    )

    if success and sorted_scores:
        result_message = "## 現在のトータルスコア\n"
        for i, (player, score) in enumerate(sorted_scores):
            rank = i + 1
            mention = await get_mention_from_player_name(interaction, player)
            result_message += f"- {mention}: {score} ({rank}位)\n"
        final_message = result_message
    else:
        final_message = message

    await interaction.response.send_message(final_message, ephemeral=not success)


# ゲームセット完了コマンド
@discord.app_commands.command(
    name="mj_end",
    description="麻雀のスコア集計を完了し、結果を出力します。",
)
async def mj_end(interaction: discord.Interaction):  # type: ignore
    guild_id = str(interaction.guild_id)
    channel_id = str(interaction.channel_id)

    success, message, sorted_scores = gameset_manager.end_gameset(guild_id, channel_id)

    if success and sorted_scores:
        result_message = "## 麻雀ゲームセット結果\n"
        for i, (player, score) in enumerate(sorted_scores):
            rank = i + 1
            mention = await get_mention_from_player_name(interaction, player)
            result_message += f"- {mention}: {score} ({rank}位)\n"
        final_message = result_message
    else:
        final_message = message

    await interaction.response.send_message(final_message, ephemeral=not success)


def setup(bot: commands.Bot):
    bot.tree.add_command(mj_start)
    bot.tree.add_command(mj_record)
    bot.tree.add_command(mj_scores)
    bot.tree.add_command(mj_end)
