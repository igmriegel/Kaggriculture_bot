"""Immutable, defensive normalization for heuristic engines.

The official environment intentionally remains the authority.  This module only
normalizes fields that are present and keeps unknown protocol details out of
strategy code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Tile:
    x: int
    y: int
    kind: str | None
    watered_today: bool = False
    yield_units: int = 0
    weeds: bool = False
    fertilizer: int = 0
    crop: str | None = None
    animal: str | None = None
    fed_today: bool = False
    cared_today: bool = False
    fertilizer_available: bool = False


@dataclass(frozen=True)
class NormalizedState:
    """The verified, strategy-facing subset of an observation."""

    money: int
    day: int
    hour: int
    step: int
    position: tuple[int, int]
    hand_positions: tuple[tuple[int, int], ...]
    tiles: tuple[Tile, ...]
    seeds: dict[str, int]
    inventory: dict[str, int]
    shed: dict[str, int]
    unit_inventories: tuple[dict[str, int], ...]
    shed_capacity: int
    prices: dict[str, float]
    demand: dict[str, int]
    time_remaining: int | None

    @classmethod
    def from_observation(cls, observation: dict[str, Any]) -> NormalizedState:
        farms = observation.get("farms", [])
        player = _integer(observation.get("player"))
        farm = farms[player] if isinstance(farms, list) and 0 <= player < len(farms) else {}
        farm = farm if isinstance(farm, dict) else {}
        position = farm.get("farmer", [0, 0])
        x = _integer(position[0]) if isinstance(position, list) and position else 0
        y = _integer(position[1]) if isinstance(position, list) and len(position) > 1 else 0
        tiles: list[Tile] = []
        for tile_y, row in enumerate(farm.get("tiles", [])):
            if not isinstance(row, list):
                continue
            for tile_x, raw in enumerate(row):
                if isinstance(raw, dict):
                    tiles.append(
                        Tile(
                            x=tile_x,
                            y=tile_y,
                            kind=_string(raw.get("kind")),
                            watered_today=bool(raw.get("watered_today", False)),
                            yield_units=_integer(raw.get("yield_units")),
                            weeds=bool(raw.get("weeds", False)),
                            fertilizer=_integer(raw.get("fertilizer")),
                            crop=_string(raw.get("crop")),
                            animal=_string(raw.get("animal")),
                            fed_today=bool(raw.get("fed_today", False)),
                            cared_today=bool(raw.get("cared_today", False)),
                            fertilizer_available=bool(raw.get("fertilizer_available", False)),
                        )
                    )
                elif raw is None:
                    tiles.append(Tile(tile_x, tile_y, None))
        private = observation.get("private", {})
        private = private if isinstance(private, dict) else {}
        market = observation.get("market", {})
        town = observation.get("town", {})
        inventories = private.get("inventories")
        unit_inventories = (
            tuple(_quantities(item) for item in inventories)
            if isinstance(inventories, list)
            else ()
        )
        shed = _quantities(private.get("shed", private.get("inventory", farm.get("inventory"))))
        hands = farm.get("hands", [])
        return cls(
            money=_integer(farm.get("money")),
            day=_integer(observation.get("day")),
            hour=_integer(observation.get("hour")),
            step=_integer(observation.get("step")),
            position=(x, y),
            hand_positions=tuple(
                (_integer(pos[0]), _integer(pos[1]))
                for pos in hands
                if isinstance(pos, list) and len(pos) >= 2
            ),
            tiles=tuple(tiles),
            seeds=_quantities(private.get("seeds")),
            inventory=shed,
            shed=shed,
            unit_inventories=unit_inventories,
            shed_capacity=_integer(observation.get("shedCapacity", 100)) or 100,
            prices=_prices(market),
            demand=_quantities(town.get("demand") if isinstance(town, dict) else {}),
            time_remaining=_optional_integer(observation.get("time_remaining")),
        )

    def tile_at_position(self) -> Tile | None:
        return next((tile for tile in self.tiles if (tile.x, tile.y) == self.position), None)

    def nearest_empty(self) -> Tile | None:
        empty = [tile for tile in self.tiles if tile.kind is None]
        if not empty:
            return None
        return min(empty, key=lambda tile: _distance(self.position, (tile.x, tile.y)))

    def units(self) -> tuple[tuple[int, int], ...]:
        return (self.position, *self.hand_positions)

    def tile_at(self, position: tuple[int, int]) -> Tile | None:
        return next((tile for tile in self.tiles if (tile.x, tile.y) == position), None)


def _integer(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _optional_integer(value: Any) -> int | None:
    return _integer(value) if value is not None else None


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _quantities(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {str(key): _integer(amount) for key, amount in value.items()}


def _prices(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    prices = value.get("prices", value)
    if not isinstance(prices, dict):
        return {}
    return {str(key): float(amount) for key, amount in prices.items() if _is_number(amount)}


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _distance(source: tuple[int, int], target: tuple[int, int]) -> int:
    return abs(source[0] - target[0]) + abs(source[1] - target[1])
