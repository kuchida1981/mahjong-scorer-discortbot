import re
from typing import List, Optional

import discord
from discord.ext import commands
from discord.ui import Button, Modal, TextInput, View

from app.core.gameset_manager import GamesetManager

# GamesetManagerのインスタンスを作成
gameset_manager = GamesetManager()


# プレイヤー名からDiscordのメンション文字列を取得するヘルパー関数
async def get_mention_from_player_name(
    interaction: discord.Interaction, player_name: str
) -> str:
    """プレイヤー名からDiscordのメンション文字列を取得する"""
    # DiscordのユーザーID形式のメンションを検出
    match = re.match(r"<@!?(\d+)>", player_name)
    if match:
        user_id = int(match.group(1))
        try:
            # ユーザーオブジェクトを取得し、表示名またはグローバル名を使用
            user = await interaction.client.fetch_user(user_id)
            return user.display_name or user.global_name or player_name
        except discord.NotFound:
            # ユーザーが見つからない場合は元のプレイヤー名を返す
            return player_name

    if interaction.guild:
        # ニックネームまたはユーザー名でメンバーを検索
        for member in interaction.guild.members:
            if member.nick == player_name or member.name == player_name:
                return member.mention
    return player_name  # 見つからない場合は元のプレイヤー名を返す


class ScoreInputModal(Modal, title="スコア入力"):
    def __init__(
        self,
        guild_id: str,
        channel_id: str,
        rule: str,
        players_count: int,
        service: str,
        selected_players: List[str],
    ):
        super().__init__()
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.rule = rule
        self.players_count = players_count
        self.service = service
        self.selected_players = selected_players
        self.score_inputs: List[TextInput] = []

        for player_name in self.selected_players:
            text_input: TextInput = TextInput(  # 型アノテーションを追加
                label=f"{player_name} のスコア",
                placeholder="例: 25000",
                required=True,
            )
            self.add_item(text_input)
            self.score_inputs.append(text_input)

    async def on_submit(self, interaction: discord.Interaction):
        parsed_scores = {}
        total_score = 0
        scores_str_parts = []

        for i, player_name in enumerate(self.selected_players):
            try:
                score = int(self.score_inputs[i].value)
                parsed_scores[player_name] = score
                total_score += score
                scores_str_parts.append(f"{player_name}:{score}")
            except ValueError:
                await interaction.response.send_message(
                    f"エラー: {player_name} のスコアが数値ではありません。再入力してください。",
                    ephemeral=True,
                )
                return

        if total_score != 0:
            await interaction.response.send_message(
                f"エラー: スコアの合計が0になりません。現在の合計: {total_score}。再入力してください。",
                ephemeral=True,
            )
            return

        scores_str = ",".join(scores_str_parts)

        success, message, sorted_scores = gameset_manager.record_game(
            self.guild_id,
            self.channel_id,
            self.rule,
            self.players_count,
            scores_str,
            self.service,
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


class PlayerSelectView(View):
    def __init__(
        self,
        guild_id: str,
        channel_id: str,
        rule: str,
        players_count: int,
        service: str,
        registered_members: List[str],
    ):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.rule = rule
        self.players_count = players_count
        self.service = service
        self.registered_members = registered_members
        self.selected_players: List[str] = []

        options = [
            discord.SelectOption(label=member, value=member)
            for member in registered_members
        ]

        self.player_select: discord.ui.Select = (
            discord.ui.Select(  # 型アノテーションを追加
                placeholder=f"{players_count}人のプレイヤーを選択してください",
                min_values=players_count,
                max_values=players_count,
                options=options,
            )
        )
        self.add_item(self.player_select)

        # コールバックを直接割り当てる (mypyエラー回避のためtype: ignoreを追加)
        self.player_select.callback = self.on_player_select  # type: ignore

    async def on_player_select(self, interaction: discord.Interaction):
        self.selected_players = self.player_select.values
        await interaction.response.send_modal(
            ScoreInputModal(
                self.guild_id,
                self.channel_id,
                self.rule,
                self.players_count,
                self.service,
                self.selected_players,
            )
        )


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
        guild_id in gameset_manager.current_gamesets
        and channel_id in gameset_manager.current_gamesets[guild_id]
        and gameset_manager.current_gamesets[guild_id][channel_id]["status"] == "active"
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


# メンバー登録コマンド
@discord.app_commands.command(
    name="mj_member", description="ゲームセットにメンバーを登録します。"
)
@discord.app_commands.describe(member_name="登録するメンバーの名前")
async def mj_member(interaction: discord.Interaction, member_name: str):  # type: ignore
    guild_id = str(interaction.guild_id)
    channel_id = str(interaction.channel_id)

    success, message = gameset_manager.add_member(guild_id, channel_id, member_name)
    await interaction.response.send_message(message, ephemeral=not success)


# メンバー一覧表示コマンド
@discord.app_commands.command(
    name="mj_member_list", description="登録されているメンバーの一覧を表示します。"
)
async def mj_member_list(interaction: discord.Interaction):  # type: ignore
    guild_id = str(interaction.guild_id)
    channel_id = str(interaction.channel_id)

    success, message, members = gameset_manager.get_members(guild_id, channel_id)

    if success and members:
        member_mentions = []
        for member_name in members:
            mention = await get_mention_from_player_name(interaction, member_name)
            member_mentions.append(mention)
        final_message = "## 登録メンバー一覧\n" + "\n".join(
            [f"- {m}" for m in member_mentions]
        )
    else:
        final_message = message

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
)
async def mj_record(
    interaction: discord.Interaction,  # type: ignore
    service: str,
    rule: str,
    players: int,
):
    guild_id = str(interaction.guild_id)
    channel_id = str(interaction.channel_id)

    # メンバーが登録されているか確認
    success, message, registered_members = gameset_manager.get_members(
        guild_id, channel_id
    )
    if not success or not registered_members:
        await interaction.response.send_message(
            message + " `/mj_member` コマンドでメンバーを登録してください。",
            ephemeral=True,
        )
        return

    # プレイヤー選択Viewを表示
    view = PlayerSelectView(
        guild_id, channel_id, rule, players, service, registered_members
    )
    await interaction.response.send_message(
        "ゲームに参加するメンバーを選択してください。", view=view, ephemeral=True
    )


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
    bot.tree.add_command(mj_member)
    bot.tree.add_command(mj_member_list)
    bot.tree.add_command(mj_record)
    bot.tree.add_command(mj_scores)
    bot.tree.add_command(mj_end)
