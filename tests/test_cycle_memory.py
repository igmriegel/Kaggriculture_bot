from __future__ import annotations

from agent.core.validation import validate_action
from agent.engines.leader_v2 import LeaderV2Engine


def _observation(
    tile: object,
    *,
    day: int = 0,
    hour: int = 0,
    step: int | None = None,
    money: int = 3000,
    shed: dict[str, int] | None = None,
    inventory: dict[str, int] | None = None,
    unlocked: list[str] | None = None,
) -> dict:
    board = [[None for _ in range(10)] for _ in range(10)]
    board[4][4] = tile
    return {
        "player": 0,
        "day": day,
        "hour": hour,
        "step": day * 24 + hour if step is None else step,
        "farms": [
            {
                "money": money,
                "farmer": [4, 4],
                "hands": [],
                "hires_today": 0,
                "unlocked_quadrants": unlocked or ["NW"],
                "tiles": board,
            }
        ],
        "private": {
            "shed": shed or {},
            "seeds": {},
            "inventories": [inventory or {}],
        },
        "market": {"prices": {"WHEAT": 25}, "inventory": {"WHEAT": 10_000}},
        "town": {"unlocked_shops": []},
    }


def test_memory_reconciles_a_plant_harvest_and_sale_cycle() -> None:
    engine = LeaderV2Engine()
    planted = {
        "kind": "PLANT",
        "crop": "WHEAT",
        "planted_day": 0,
        "yield_units": 0,
        "watered_today": False,
    }

    assert engine.act(_observation(planted, step=0, money=100))["farmer"] == ["WATER"]
    watered = dict(planted, watered_today=True, yield_units=1)
    assert engine.act(_observation(watered, day=2, hour=0, money=100))["farmer"] == ["HARVEST"]
    harvested = _observation(None, day=2, hour=1, inventory={"WHEAT": 1}, money=100)
    assert engine.act(harvested)["farmer"] == ["DROP"]
    stored = _observation(None, day=2, hour=2, shed={"WHEAT": 1}, money=100)
    assert ["SELL", "WHEAT", 1] in engine.act(stored)["market"]
    sold = _observation(None, day=2, hour=3, shed={}, money=125)
    engine.finalize_cycle(sold)

    metrics = engine.cycle_metrics()
    assert metrics["plant_harvest_sale_cycles"] == 1
    assert metrics["plan_observation_divergences"] == 0
    assert metrics["cash_spent"] == 0


def test_failed_intent_is_blocked_and_only_that_step_is_replanned() -> None:
    engine = LeaderV2Engine()
    plant = {"kind": "PLANT", "crop": "WHEAT", "planted_day": 0, "yield_units": 0}
    assert engine.act(_observation(plant, step=0))["farmer"] == ["WATER"]

    # The official observation reports no watering effect.  The next plan must
    # not blindly emit the same invalidated intent again.
    divergent = _observation(plant, hour=1, step=1)
    action = engine.act(divergent)
    assert action["farmer"] != ["WATER"]
    metrics = engine.cycle_metrics()
    assert metrics["plan_observation_divergences"] == 1
    assert metrics["commitments_replanned"] == 1
    assert metrics["commitment_status"]["blocked"] >= 1


def test_expansion_waits_for_animal_recovery_chain() -> None:
    animal = {"kind": "PASTURE", "animal": "COW", "fed_today": False}
    action = LeaderV2Engine().act(
        _observation(
            animal,
            day=6,
            hour=2,
            money=10_000,
            shed={"WHEAT": 1},
            unlocked=["NW", "NE"],
        )
    )

    assert ["BUY_LAND"] not in action["market"]


def test_one_unit_feed_remains_legal_through_memory_reconciliation() -> None:
    engine = LeaderV2Engine()
    hungry = {"kind": "PASTURE", "animal": "COW", "fed_today": False}
    observation = _observation(hungry, shed={"WHEAT": 1})
    action = engine.act(observation)
    assert action["farmer"] == ["PICKUP", "WHEAT", 1]
    validated, reason = validate_action(action, observation)
    assert reason is None
    assert validated.model_dump() == action
