"""State Value Function & Feature Extractor for Strategic Evaluation (V11 Phase 4)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np

from agent.core.state import NormalizedState
from agent.domain.economics import PRODUCTS

FEATURE_NAMES = (
    # Temporal (2)
    "day_norm",
    "hour_norm",
    # Financial (3)
    "money_norm",
    "money_delta_norm",
    "opp_money_norm",
    # Farm composition (4)
    "plant_count_norm",
    "animal_count_norm",
    "quadrant_count_norm",
    "worker_count_norm",
    # Per-crop counts (5)
    "wheat_count",
    "carrot_count",
    "tomato_count",
    "strawberry_count",
    "melon_count",
    # Livestock counts (3)
    "cow_count",
    "sheep_count",
    "goose_count",
    # Shed inventory (5)
    "shed_wheat",
    "shed_strawberry",
    "shed_melon",
    "shed_milk",
    "shed_wool",
    # Market prices (9)
    *[f"price_{p.lower()}" for p in PRODUCTS],
    # Opponent features (2)
    "opp_plants_norm",
    "opp_animals_norm",
    # Shops unlocked (1)
    "shops_count_norm",
)


def extract_state_features(state: NormalizedState) -> np.ndarray:
    """Extract 34 normalized numerical features from game state for value function evaluation."""
    my_plants = [t for t in state.tiles if t.kind == "PLANT"]
    my_animals = [t for t in state.tiles if t.animal]

    crop_counts = {c: 0 for c in ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON")}
    for t in my_plants:
        if t.crop in crop_counts:
            crop_counts[t.crop] += 1

    cow_cnt = sum(1 for t in my_animals if t.animal == "COW")
    sheep_cnt = sum(1 for t in my_animals if t.animal == "SHEEP")
    goose_cnt = sum(1 for t in my_animals if t.animal == "GOOSE")

    opp_plants = sum(1 for t in state.opponent_tiles if t.kind == "PLANT")
    opp_animals = sum(1 for t in state.opponent_tiles if t.animal)

    features = [
        # Temporal (2)
        state.day / 30.0,
        state.hour / 24.0,
        # Financial (3)
        state.money / 100_000.0,
        (state.money - state.opponent_money) / 100_000.0,
        state.opponent_money / 100_000.0,
        # Farm composition (4)
        len(my_plants) / 25.0,
        len(my_animals) / 14.0,
        len(state.unlocked_quadrants) / 4.0,
        (1 + len(state.hand_positions)) / 6.0,
        # Per-crop counts (5)
        crop_counts["WHEAT"] / 10.0,
        crop_counts["CARROT"] / 10.0,
        crop_counts["TOMATO"] / 10.0,
        crop_counts["STRAWBERRY"] / 10.0,
        crop_counts["MELON"] / 10.0,
        # Livestock counts (3)
        cow_cnt / 7.0,
        sheep_cnt / 7.0,
        goose_cnt / 7.0,
        # Shed inventory (5)
        state.shed.get("WHEAT", 0) / 20.0,
        state.shed.get("STRAWBERRY", 0) / 10.0,
        state.shed.get("MELON", 0) / 10.0,
        state.shed.get("MILK", 0) / 10.0,
        state.shed.get("WOOL", 0) / 10.0,
        # Market prices (9)
        *[state.prices.get(p, 0) / 300.0 for p in PRODUCTS],
        # Opponent features (2)
        opp_plants / 25.0,
        opp_animals / 14.0,
        # Shops unlocked (1)
        len(state.shops) / 8.0,
    ]

    return np.array(features, dtype=np.float32)


class StateValueEvaluator:
    """Lightweight state value evaluator using linear/tree models trained offline on self-play."""

    def __init__(self, model_path: str | Path | None = None) -> None:
        self.model: Any | None = None
        if model_path is None:
            model_path = Path(__file__).parent.parent / "engines" / "value_function.joblib"

        if os.path.exists(model_path):
            try:
                import joblib

                self.model = joblib.load(model_path)
            except Exception:
                self.model = None

    def evaluate(self, state: NormalizedState) -> float:
        """Return projected final margin for the given state."""
        features = extract_state_features(state)
        if self.model is not None:
            try:
                pred = float(self.model.predict(features.reshape(1, -1))[0])
                return pred
            except Exception:
                pass

        # Robust heuristic fallback when no model file is loaded:
        # Estimate net wealth: money + estimated asset value - opp money
        my_assets = (
            state.money
            + sum(state.shed.values()) * 50
            + sum(1 for t in state.tiles if t.animal) * 450
            + sum(1 for t in state.tiles if t.kind == "PLANT") * 100
        )
        opp_assets = (
            state.opponent_money
            + sum(1 for t in state.opponent_tiles if t.animal) * 450
            + sum(1 for t in state.opponent_tiles if t.kind == "PLANT") * 100
        )
        return float(my_assets - opp_assets)
