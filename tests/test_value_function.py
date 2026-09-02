"""Unit tests for State Value Function & Feature Extractor (V11 Phase 4)."""

import numpy as np

from agent.core.state import NormalizedState
from agent.domain.value_function import StateValueEvaluator, extract_state_features


def test_extract_state_features_shape() -> None:
    obs = {
        "step": 120,
        "day": 5,
        "hour": 0,
        "player": 0,
        "farms": [
            {
                "money": 3000,
                "farmer": [0, 0],
                "hands": [],
                "unlocked_quadrants": [1],
                "shed": {"WHEAT": 5, "MILK": 2},
                "tiles": [],
            },
            {
                "money": 2800,
                "farmer": [0, 0],
                "tiles": [],
            },
        ],
        "market": {
            "prices": {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120, "MELON": 250},
            "shops": ["BAKERY", "PIZZA_SHOP"],
            "inventory": {},
        },
    }
    state = NormalizedState.from_observation(obs)
    feats = extract_state_features(state)

    assert isinstance(feats, np.ndarray)
    assert feats.dtype == np.float32
    assert len(feats) == 34
    assert not np.isnan(feats).any()


def test_state_value_evaluator_fallback() -> None:
    evaluator = StateValueEvaluator(model_path="non_existent_model.joblib")
    obs = {
        "step": 120,
        "day": 5,
        "hour": 0,
        "player": 0,
        "farms": [
            {
                "money": 3000,
                "farmer": [0, 0],
                "shed": {"WHEAT": 5},
                "unlocked_quadrants": [1],
                "tiles": [],
            },
            {
                "money": 2800,
                "farmer": [0, 0],
                "tiles": [],
            },
        ],
        "market": {"prices": {}, "shops": [], "inventory": {}},
    }
    state = NormalizedState.from_observation(obs)
    val = evaluator.evaluate(state)

    assert isinstance(val, float)
    assert val > 0.0
