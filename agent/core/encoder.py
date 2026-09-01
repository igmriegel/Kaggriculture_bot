"""Vector state representation and feature encoder for ML/Search engines."""

from __future__ import annotations

import math
from dataclasses import dataclass

from agent.core.state import NormalizedState


@dataclass(frozen=True)
class EncodedFeatures:
    """Normalized numerical feature representation of a game observation."""

    vector: tuple[float, ...]
    feature_names: tuple[str, ...]

    def to_dict(self) -> dict[str, float]:
        return dict(zip(self.feature_names, self.vector, strict=True))


class StateEncoder:
    """Encodes NormalizedState into a fixed-size float vector for evaluation and ML."""

    CROPS: tuple[str, ...] = ("WHEAT", "CORN", "TOMATO", "POTATO", "MELON", "STRAWBERRY")
    ANIMALS: tuple[str, ...] = ("COW", "SHEEP", "GOOSE")
    ITEMS: tuple[str, ...] = (
        "WHEAT",
        "CORN",
        "TOMATO",
        "POTATO",
        "MELON",
        "STRAWBERRY",
        "MILK",
        "WOOL",
        "EGG",
        "FERTILIZER",
    )

    def encode(self, state: NormalizedState) -> EncodedFeatures:
        names: list[str] = []
        vals: list[float] = []

        # Time features
        names.extend(["day_norm", "hour_norm", "step_norm", "season_progress"])
        vals.extend(
            [
                state.day / 30.0,
                state.hour / 24.0,
                state.step / (30 * 24.0),
                (state.day % 10) / 10.0,
            ]
        )

        # Financial & Inventory features
        names.extend(["money_log", "opponent_money_log", "money_ratio"])
        m_self = max(0.0, float(state.money))
        m_opp = max(0.0, float(state.opponent_money))
        vals.extend(
            [
                math.log1p(m_self) / 10.0,
                math.log1p(m_opp) / 10.0,
                m_self / max(1.0, m_self + m_opp),
            ]
        )

        # Position features
        bs = max(1, state.board_size)
        names.extend(["farmer_x_norm", "farmer_y_norm", "shed_dist_norm"])
        vals.extend(
            [
                state.position[0] / float(bs),
                state.position[1] / float(bs),
                state.min_shed_distance(state.position) / float(2 * bs),
            ]
        )

        # Tile summary
        total_tiles = len(state.tiles) or 1
        plant_tiles = sum(1 for t in state.tiles if t.kind == "PLANT")
        watered_tiles = sum(1 for t in state.tiles if t.kind == "PLANT" and t.watered_today)
        harvestable_tiles = sum(1 for t in state.tiles if t.kind == "PLANT" and t.yield_units > 0)
        livestock_tiles = sum(1 for t in state.tiles if t.kind == "LIVESTOCK")
        weedy_tiles = sum(1 for t in state.tiles if t.weeds)

        names.extend(
            [
                "plant_ratio",
                "watered_ratio",
                "harvestable_ratio",
                "livestock_ratio",
                "weeds_ratio",
            ]
        )
        vals.extend(
            [
                plant_tiles / float(total_tiles),
                watered_tiles / float(max(1, plant_tiles)),
                harvestable_tiles / float(max(1, plant_tiles)),
                livestock_tiles / float(total_tiles),
                weedy_tiles / float(total_tiles),
            ]
        )

        # Crop counts
        for crop in self.CROPS:
            count = sum(1 for t in state.tiles if t.crop == crop)
            names.append(f"crop_count_{crop.lower()}")
            vals.append(count / float(total_tiles))

        # Animal counts
        for animal in self.ANIMALS:
            count = sum(1 for t in state.tiles if t.animal == animal)
            names.append(f"animal_count_{animal.lower()}")
            vals.append(count / 10.0)

        # Inventory quantities
        total_shed = sum(state.shed.values()) or 0
        names.append("shed_utilization")
        vals.append(min(1.0, total_shed / float(max(1, state.shed_capacity))))

        for item in self.ITEMS:
            qty = state.shed.get(item, 0)
            names.append(f"shed_qty_{item.lower()}")
            vals.append(math.log1p(qty) / 5.0)

        # Seeds
        for crop in self.CROPS:
            qty = state.seeds.get(crop, 0)
            names.append(f"seed_qty_{crop.lower()}")
            vals.append(math.log1p(qty) / 5.0)

        # Market Prices
        for item in self.ITEMS:
            price = state.prices.get(item, 0.0)
            names.append(f"price_{item.lower()}")
            vals.append(price / 100.0)

        # Opponent overview
        opp_total = len(state.opponent_tiles) or 1
        opp_plants = sum(1 for t in state.opponent_tiles if t.kind == "PLANT")
        names.extend(["opp_plant_ratio", "opp_hands_count"])
        vals.extend(
            [
                opp_plants / float(opp_total),
                state.opponent_hand_count / 5.0,
            ]
        )

        return EncodedFeatures(vector=tuple(vals), feature_names=tuple(names))
