import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.core.data_manager import load_gamesets, save_gamesets

# 現在進行中のゲームセットを管理する辞書
# { guild_id: { channel_id: { "status": "active", "games": [], "members": {} } } }
current_gamesets = load_gamesets()


class GamesetManager:
    def __init__(self):
        self.current_gamesets = load_gamesets()

    def _get_gameset_data(self, guild_id: str, channel_id: str) -> Dict[str, Any]:
        if guild_id not in self.current_gamesets:
            self.current_gamesets[guild_id] = {}
        if channel_id not in self.current_gamesets[guild_id]:
            self.current_gamesets[guild_id][channel_id] = {
                "status": "inactive",
                "games": [],
                "members": {},
            }
        return self.current_gamesets[guild_id][channel_id]

    def _save_current_gamesets(self) -> None:
        save_gamesets(self.current_gamesets)

    def add_member(
        self, guild_id: str, channel_id: str, member_name: str
    ) -> Tuple[bool, str]:
        gameset_data = self._get_gameset_data(guild_id, channel_id)
        if member_name in gameset_data["members"]:
            return False, f"メンバー '{member_name}' は既に登録されています。"
        gameset_data["members"][member_name] = 0
        self._save_current_gamesets()
        return True, f"メンバー '{member_name}' を登録しました。"

    def get_members(
        self, guild_id: str, channel_id: str
    ) -> Tuple[bool, str, Optional[List[str]]]:
        gameset_data = self._get_gameset_data(guild_id, channel_id)
        if not gameset_data["members"]:
            return False, "登録されているメンバーがいません。", None
        return True, "登録メンバー一覧", list(gameset_data["members"].keys())

    def start_gameset(self, guild_id: str, channel_id: str) -> Tuple[bool, str]:
        gameset_data = self._get_gameset_data(guild_id, channel_id)

        if gameset_data["status"] == "active":
            # 既存のゲームセットを破棄
            gameset_data.update(
                {
                    "status": "inactive",
                    "games": [],
                    "members": {},
                }
            )
            self._save_current_gamesets()
            # 新しいゲームセットを開始
            gameset_data.update(
                {
                    "status": "active",
                    "games": [],
                    "members": {},
                }
            )
            self._save_current_gamesets()
            return (
                True,
                "既存のゲームセットを破棄し、新しい麻雀のスコア集計を開始します。",
            )
        else:
            gameset_data.update(
                {
                    "status": "active",
                    "games": [],
                    "members": {},
                }
            )
            self._save_current_gamesets()
            return (
                True,
                "麻雀のスコア集計を開始します。",
            )

    def record_game(
        self,
        guild_id: str,
        channel_id: str,
        rule: str,
        players_count: int,
        scores_str: str,
        service: str,
    ) -> Tuple[bool, str, Optional[List[Tuple[str, int]]]]:
        gameset_data = self._get_gameset_data(guild_id, channel_id)

        if gameset_data["status"] != "active":
            return (
                False,
                "このチャンネルで進行中のゲームセットがありません。",
                None,
            )

        expected_players_count = players_count

        parsed_scores = {}
        total_score = 0

        score_entries = [s.strip() for s in scores_str.split(",")]

        if len(score_entries) != expected_players_count:
            return (
                False,
                f"{expected_players_count}人分のスコアを入力してください。現在 {len(score_entries)}人分のスコアが入力されています。",
                None,
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
                        None,
                    )
                player_names.append(player_name)
                parsed_scores[player_name] = score
                total_score += score
            except ValueError:
                return (
                    False,
                    "スコアの形式が正しくありません。`名前:スコア` の形式で入力してください (例: `@player1:25000`)。",
                    None,
                )
            except IndexError:
                return (
                    False,
                    "スコアの形式が正しくありません。`名前:スコア` の形式で入力してください (例: `@player1:25000`)。",
                    None,
                )

        # ゼロサムチェック
        if total_score != 0:
            return (
                False,
                f"スコアの合計が0になりません。現在の合計: {total_score}。再入力してください。",
                None,
            )

        game_data = {
            "rule": rule,
            "players_count": players_count,
            "scores": parsed_scores,
            "service": service,
        }
        gameset_data["games"].append(game_data)

        # メンバーのスコアを更新
        for player_name, score in parsed_scores.items():
            if player_name not in gameset_data["members"]:
                gameset_data["members"][player_name] = 0
            gameset_data["members"][player_name] += score

        self._save_current_gamesets()

        # 順位を計算し、結果を返す
        sorted_game_scores = sorted(
            parsed_scores.items(), key=lambda item: item[1], reverse=True
        )
        return True, "ゲーム結果を記録しました。", sorted_game_scores

    def get_current_scores(
        self, guild_id: str, channel_id: str
    ) -> Tuple[bool, str, Optional[List[Tuple[str, int]]]]:
        gameset_data = self._get_gameset_data(guild_id, channel_id)

        if gameset_data["status"] != "active":
            return (
                False,
                "このチャンネルで進行中のゲームセットがありません。",
                None,
            )

        total_scores = gameset_data["members"]

        if not total_scores:
            return False, "まだゲームが記録されていません。", None

        # スコアを降順にソート
        sorted_scores = sorted(
            total_scores.items(), key=lambda item: item[1], reverse=True
        )

        return True, "現在のトータルスコア", sorted_scores

    def end_gameset(
        self, guild_id: str, channel_id: str
    ) -> Tuple[bool, str, Optional[List[Tuple[str, int]]]]:
        gameset_data = self._get_gameset_data(guild_id, channel_id)

        if gameset_data["status"] != "active":
            return False, "このチャンネルで進行中のゲームセットがありません。", None

        total_scores = gameset_data["members"]

        # ゲーム記録がない場合、メッセージを返さずにゲームセットを閉じる
        if not total_scores:
            gameset_data["status"] = "inactive"
            self._save_current_gamesets()
            # current_gamesetsもクリアする
            gameset_data.update(
                {
                    "status": "inactive",
                    "games": [],
                    "members": {},
                }
            )
            return (
                True,
                "ゲームセットを閉じました。記録されたゲームはありませんでした。",
                None,
            )

        # スコアを降順にソート
        sorted_scores = sorted(
            total_scores.items(), key=lambda item: item[1], reverse=True
        )

        # ゲームセットを非アクティブにする
        gameset_data["status"] = "inactive"
        self._save_current_gamesets()

        # ファイルをリネーム
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        new_file_name = f"gamesets.{timestamp}.json"
        if os.path.exists("gamesets.json"):  # DATA_FILEはdata_managerにあるため直接指定
            os.rename("gamesets.json", new_file_name)
            # リネーム後、gamesets.jsonを空にする
            save_gamesets({})  # data_managerのsave_gamesetsを使用
            # current_gamesetsもクリアする
            gameset_data.update(
                {
                    "status": "inactive",
                    "games": [],
                    "members": {},
                }
            )

        return True, "麻雀ゲームセット結果", sorted_scores
