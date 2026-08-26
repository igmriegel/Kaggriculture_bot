"""ROI calculations, opponent crop tracking, and harvest horizon planning."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from agent.core.state import NormalizedState, Tile
from agent.domain.economics import MARKET_I0, market_price

CROPS_SPEC = {
    "WHEAT": {
        "seed": 10,
        "first_yield_day": 2,
        "max_yield_day": 4,
        "interval": 0,
        "max_yield": 6,
        "ongoing": False,
        "product": "WHEAT",
    },
    "CARROT": {
        "seed": 20,
        "first_yield_day": 2,
        "max_yield_day": 3,
        "interval": 0,
        "max_yield": 4,
        "ongoing": False,
        "product": "CARROT",
    },
    "TOMATO": {
        "seed": 50,
        "first_yield_day": 8,
        "max_yield_day": 8,
        "interval": 1,
        "max_yield": 4,
        "ongoing": True,
        "product": "TOMATO",
    },
    "STRAWBERRY": {
        "seed": 100,
        "first_yield_day": 10,
        "max_yield_day": 10,
        "interval": 2,
        "max_yield": 4,
        "ongoing": True,
        "product": "STRAWBERRY",
    },
    "MELON": {
        "seed": 80,
        "first_yield_day": 10,
        "max_yield_day": 12,
        "interval": 0,
        "max_yield": 6,
        "ongoing": False,
        "product": "MELON",
    },
}

TOTAL_SEASON_DAYS = 30


@dataclass(frozen=True)
class CropROI:
    crop: str
    expected_profit_per_day: float
    expected_revenue: float
    seed_cost: int
    days_to_first_yield: int
    closing_day: int
    viable_to_plant: bool


def calculate_closing_day(crop: str, total_days: int = TOTAL_SEASON_DAYS) -> int:
    """Last day where planting this crop still yields before season end."""
    spec = CROPS_SPEC.get(crop)
    if not spec:
        return 0
    return total_days - int(spec["first_yield_day"])


def estimate_opponent_expected_harvests(opponent_tiles: tuple[Tile, ...]) -> dict[str, int]:
    """Track opponent planted crops and project expected units coming to market."""
    projected: dict[str, int] = {}
    for tile in opponent_tiles:
        if tile.kind == "PLANT" and tile.crop:
            crop = tile.crop
            spec = CROPS_SPEC.get(crop, {})
            max_yield = int(spec.get("max_yield", 1))
            projected[crop] = projected.get(crop, 0) + max_yield
        elif tile.animal == "GOOSE":
            projected["EGG"] = projected.get("EGG", 0) + 10
    return projected


def calculate_dynamic_harvest_price(
    crop: str,
    state: NormalizedState,
    harvest_day: int,
    *,
    overrides: Mapping[str, Mapping[str, object]] | None = None,
) -> int:
    """Project market price at the exact moment this crop batch will be harvested."""
    from agent.domain.economics import PRODUCTS, SHOPS

    turns_to_harvest = max(0, (harvest_day - state.day) * 24 - state.hour)
    projected_market = dict(state.market_inventory)

    # 1. Town consumption drainage projection up to harvest turn
    for future_step in range(state.step, state.step + turns_to_harvest):
        if future_step % 4 == 0:
            for shop in state.shops:
                for item in SHOPS.get(shop, ()):
                    projected_market[item] -= 2 if len(SHOPS[shop]) == 1 else 1
        if future_step % 24 == 0:
            for item in PRODUCTS[:-1]:
                projected_market[item] -= 1

    # 2. Opponent supply arriving before/at harvest
    opp_harvests = estimate_opponent_expected_harvests(state.opponent_tiles)
    product = str(CROPS_SPEC[crop]["product"])
    projected_inv = projected_market.get(product, MARKET_I0) + opp_harvests.get(product, 0)

    return market_price(product, projected_inv, overrides)


def evaluate_crops_roi(
    state: NormalizedState,
    *,
    fertilizer_available: bool = False,
    overrides: Mapping[str, Mapping[str, object]] | None = None,
) -> dict[str, CropROI]:
    """Calculate expected crop ROI using dynamic harvest-time forecasting."""
    results: dict[str, CropROI] = {}
    days_remaining = max(0, TOTAL_SEASON_DAYS - state.day)

    for crop, spec in CROPS_SPEC.items():
        closing_day = calculate_closing_day(crop)
        first_yield = int(spec["first_yield_day"])
        max_yield_day = int(spec["max_yield_day"])
        seed_cost = int(spec["seed"])
        is_ongoing = bool(spec["ongoing"])
        interval = int(spec["interval"])
        base_max_yield = int(spec["max_yield"])

        if state.day > closing_day:
            results[crop] = CropROI(
                crop=crop,
                expected_profit_per_day=-1.0,
                expected_revenue=0.0,
                seed_cost=seed_cost,
                days_to_first_yield=first_yield,
                closing_day=closing_day,
                viable_to_plant=False,
            )
            continue

        first_harvest_day = min(TOTAL_SEASON_DAYS, state.day + first_yield)
        est_unit_price = calculate_dynamic_harvest_price(
            crop, state, first_harvest_day, overrides=overrides
        )

        if not is_ongoing:
            # Yield units accumulate during window [ (max_yield_day+1)//2, max_yield_day ]
            window_len = max_yield_day - ((max_yield_day + 1) // 2) + 1
            yield_units = min(base_max_yield, window_len)
            revenue = float(yield_units * est_unit_price)
            cycle_days = first_yield
            profit = revenue - seed_cost
            # Land yield velocity: Net profit generated per tile per day of land occupancy
            profit_per_day = profit / max(1, cycle_days)
        else:
            days_productive = max(0, days_remaining - first_yield)
            harvests = 1 + (days_productive // max(1, interval + 1))
            # Ongoing crops yield 2 units base or 4 units if fertilized
            per_harvest_yield = 3.5 if fertilizer_available else 2.0
            total_units = harvests * per_harvest_yield
            revenue = float(total_units * est_unit_price)
            profit = revenue - seed_cost
            effective_cycle_days = first_yield + max(0, harvests - 1) * (interval + 1)
            profit_per_day = profit / max(1, effective_cycle_days)

        results[crop] = CropROI(
            crop=crop,
            expected_profit_per_day=profit_per_day,
            expected_revenue=revenue,
            seed_cost=seed_cost,
            days_to_first_yield=first_yield,
            closing_day=closing_day,
            viable_to_plant=profit > 0 and state.day <= closing_day,
        )

    return results


def best_crop_to_plant(
    state: NormalizedState,
    *,
    min_budget: int = 0,
    overrides: Mapping[str, Mapping[str, object]] | None = None,
) -> str | None:
    """Return the crop with highest expected daily profit that the bot can afford."""
    rois = evaluate_crops_roi(state, overrides=overrides)
    viable = [
        roi
        for roi in rois.values()
        if roi.viable_to_plant and state.money >= min_budget + roi.seed_cost
    ]
    if not viable:
        return None
    viable.sort(key=lambda r: r.expected_profit_per_day, reverse=True)
    return viable[0].crop
