from typing import Any, Dict, List

from pydantic import BaseModel, Field, RootModel


class Game(BaseModel):
    rule: str
    players_count: int
    scores: Dict[str, int]
    service: str


class Gameset(BaseModel):
    status: str
    games: List[Game]
    members: Dict[str, int]


class GamesetsRoot(RootModel[Dict[str, Dict[str, Gameset]]]):
    root: Dict[str, Dict[str, Gameset]] = Field(default_factory=dict)

    def __getitem__(self, guild_id: str) -> Dict[str, Gameset]:
        return self.root[guild_id]

    def __setitem__(self, guild_id: str, value: Dict[str, Gameset]):
        self.root[guild_id] = value

    def __contains__(self, guild_id: str) -> bool:
        return guild_id in self.root

    def get(self, guild_id: str, default: Any = None) -> Dict[str, Gameset]:
        return self.root.get(guild_id, default)
