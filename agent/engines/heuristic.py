"""Conservative, deterministic MVP heuristic."""

from typing import Any

from agent.core.contracts import Action


class ConservativeHeuristic:
    """Prioritize survival and simple wheat turnover before expansion."""

    def act(self, obs: dict[str, Any]) -> dict[str, list[Any]]:
        farm = self._own_farm(obs)
        position = farm.get("farmer", [0, 0])
        tile = self._tile_at(farm, position)
        if isinstance(tile, dict) and tile.get("kind") == "PLANT":
            if not tile.get("watered_today", False):
                return Action(farmer=["WATER"]).model_dump()
            if int(tile.get("yield_units", 0)) > 0:
                return Action(farmer=["HARVEST"]).model_dump()
        seeds = obs.get("private", {}).get("seeds", {})
        if tile is None and int(seeds.get("WHEAT", 0)) > 0:
            return Action(farmer=["PLANT", "WHEAT"]).model_dump()
        if obs.get("hour", 0) == 0 and int(farm.get("money", 0)) >= 10:
            return Action(farmer=["PASS"], market=[["BUY_SEED", "WHEAT", 1]]).model_dump()
        return self._move_toward_empty(farm, position)

    @staticmethod
    def _own_farm(obs: dict[str, Any]) -> dict[str, Any]:
        farms = obs.get("farms", [])
        player = int(obs.get("player", 0))
        return farms[player] if 0 <= player < len(farms) else {}

    @staticmethod
    def _tile_at(farm: dict[str, Any], position: list[Any]) -> Any:
        tiles = farm.get("tiles", [])
        x, y = (int(position[0]), int(position[1])) if len(position) >= 2 else (0, 0)
        return tiles[y][x] if 0 <= y < len(tiles) and 0 <= x < len(tiles[y]) else "LOCKED"

    @staticmethod
    def _move_toward_empty(farm: dict[str, Any], position: list[Any]) -> dict[str, list[Any]]:
        tiles = farm.get("tiles", [])
        x, y = int(position[0]), int(position[1])
        for target_y, row in enumerate(tiles):
            for target_x, tile in enumerate(row):
                if tile is None:
                    if x < target_x:
                        return Action(farmer=["EAST"]).model_dump()
                    if x > target_x:
                        return Action(farmer=["WEST"]).model_dump()
                    if y < target_y:
                        return Action(farmer=["SOUTH"]).model_dump()
                    if y > target_y:
                        return Action(farmer=["NORTH"]).model_dump()
        return Action.pass_action().model_dump()
