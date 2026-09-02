"""Online Opponent Behavioral Tracker for real-time strategy adjustment."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.core.state import NormalizedState, Tile


@dataclass
class OpponentProfile:
    """Accumulated behavioral profile of the opponent, updated each turn."""

    # Crop preferences (cumulative tile count observed)
    crop_counts: dict[str, int] = field(default_factory=dict)

    # Financial trajectory (step, money)
    money_history: list[tuple[int, int]] = field(default_factory=list)

    # Harvest timing patterns
    last_harvest_step: dict[str, int] = field(default_factory=dict)
    harvest_intervals: dict[str, list[int]] = field(default_factory=dict)

    # Derived metrics
    estimated_sell_timing: str = "immediate"  # "immediate", "bulk"
    aggression_score: float = 0.5  # 0.0 (passive) to 1.0 (aggressive)
    crop_diversity: float = 0.5  # 0.0 (monoculture) to 1.0 (high diversity)


class OpponentTracker:
    """Tracks opponent behavior across turns and builds a real-time profile."""

    def __init__(self) -> None:
        self.profile = OpponentProfile()
        self._prev_opp_tiles: tuple[Tile, ...] | None = None
        self._prev_opp_money: int | None = None

    def reset(self) -> None:
        self.profile = OpponentProfile()
        self._prev_opp_tiles = None
        self._prev_opp_money = None

    def update(self, state: NormalizedState) -> OpponentProfile:
        """Update profile from current observation. Called once per turn."""
        # 1. Track crop composition
        for tile in state.opponent_tiles:
            if tile.kind == "PLANT" and tile.crop:
                key = tile.crop
                self.profile.crop_counts[key] = self.profile.crop_counts.get(key, 0) + 1

        # 2. Track money trajectory
        self.profile.money_history.append((state.step, state.opponent_money))

        # 3. Detect harvest events (yield_units drops to 0)
        if self._prev_opp_tiles is not None and len(self._prev_opp_tiles) == len(
            state.opponent_tiles
        ):
            for prev, curr in zip(
                self._prev_opp_tiles, state.opponent_tiles, strict=False
            ):
                if prev.yield_units > 0 and curr.yield_units == 0:
                    animal_map = {"GOOSE": "EGG", "COW": "MILK", "SHEEP": "WOOL"}
                    crop = prev.crop or animal_map.get(prev.animal or "")
                    if crop:
                        prev_step = self.profile.last_harvest_step.get(crop, 0)
                        if prev_step > 0:
                            interval = state.step - prev_step
                            self.profile.harvest_intervals.setdefault(crop, []).append(interval)
                        self.profile.last_harvest_step[crop] = state.step

        # 4. Detect sell behavior (money jumps > $500)
        if self._prev_opp_money is not None:
            delta = state.opponent_money - self._prev_opp_money
            if delta > 500:
                self.profile.estimated_sell_timing = "bulk"
            elif delta > 0 and state.step % 24 < 12:
                self.profile.estimated_sell_timing = "immediate"

        # 5. Compute aggression score
        animal_count = sum(1 for t in state.opponent_tiles if t.animal)
        plant_count = sum(1 for t in state.opponent_tiles if t.kind == "PLANT")
        if state.day > 0:
            expansion_rate = (animal_count + plant_count) / max(1, state.day)
            self.profile.aggression_score = min(1.0, expansion_rate / 3.0)

        # 6. Compute crop diversity (normalized Shannon entropy)
        total = sum(self.profile.crop_counts.values())
        if total > 0:
            probs = [c / total for c in self.profile.crop_counts.values()]
            entropy = -sum(p * math.log2(p) for p in probs if p > 0)
            max_e = math.log2(max(1, len(self.profile.crop_counts)))
            self.profile.crop_diversity = entropy / max(0.01, max_e) if max_e > 0 else 0.0

        self._prev_opp_tiles = state.opponent_tiles
        self._prev_opp_money = state.opponent_money
        return self.profile

    def predict_opponent_supply_at(
        self, state: NormalizedState, target_day: int
    ) -> dict[str, int]:
        """Project opponent crop supply arriving at market by target_day."""
        supply: dict[str, int] = {}
        for tile in state.opponent_tiles:
            if tile.kind == "PLANT" and tile.crop:
                # Estimate when this crop will mature
                from agent.domain.roi import CROPS_SPEC

                spec = CROPS_SPEC.get(tile.crop, {})
                maturity = int(spec.get("first_yield_day", 2))
                planted = tile.planted_day or state.day
                harvest_day = planted + maturity
                if harvest_day <= target_day:
                    yield_units = int(spec.get("max_yield", 4))
                    supply[tile.crop] = supply.get(tile.crop, 0) + yield_units
            elif tile.animal == "GOOSE":
                supply["EGG"] = supply.get("EGG", 0) + 2 * max(0, target_day - state.day)
        return supply
