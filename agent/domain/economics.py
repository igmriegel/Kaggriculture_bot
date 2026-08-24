"""Pure projection of the official dynamic-market rules."""

from __future__ import annotations

import math
from collections.abc import Mapping

PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")
MARKET_I0 = 10_000
MARKET = {
    "WHEAT": (25, 400, "sqrt", 0.80, "log", 0.20),
    "CARROT": (35, 450, "hinge", 1.0, "sqrt", 0.70),
    "TOMATO": (60, 200, "hinge", 0.40, "sqrt", 0.60),
    "STRAWBERRY": (120, 100, "sqrt", 0.70, "linear", 1.60),
    "MELON": (250, 300, "log", 0.20, "sq", 3.60),
    "EGG": (50, 332, "hinge", 0.40, "log", 0.20),
    "MILK": (160, 122, "sqrt", 0.60, "linear", 1.60),
    "WOOL": (200, 105, "log", 0.20, "sq", 3.20),
    "FERTILIZER": (100, 200, "linear", 0.40, "linear", 0.40),
}
SHOPS = {
    "BAKERY": ("EGG", "WHEAT"),
    "PIZZA_SHOP": ("MILK", "TOMATO", "WHEAT"),
    "BRUNCH_SPOT": ("EGG", "WHEAT", "STRAWBERRY"),
    "YARN_STORE": ("WOOL",),
    "ICE_CREAM_SHOP": ("STRAWBERRY", "MILK", "WHEAT"),
    "PET_CAFE": ("CARROT",),
    "SMOOTHIE_SHOP": ("STRAWBERRY", "MILK"),
    "FARMERS_MARKET": ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY"),
}


def market_price(
    item: str, inventory: int, overrides: Mapping[str, Mapping[str, object]] | None = None
) -> int:
    """Official price curve, including the floor and sparse configuration overrides."""
    base, capacity, below, below_target, above, above_target = MARKET[item]
    patch = overrides.get(item, {}) if overrides else {}
    base = _integer(patch.get("base"), base)
    capacity = _integer(patch.get("T"), capacity)
    i0 = _integer(patch.get("I0"), MARKET_I0)
    below = str(patch.get("below_func", below))
    below_target = _number(patch.get("below_target"), below_target)
    above = str(patch.get("above_func", above))
    above_target = _number(patch.get("above_target"), above_target)
    function, target, distance = (
        (below, below_target, i0 - inventory)
        if inventory < i0
        else (above, above_target, inventory - i0)
    )
    amplitude = target * base / _shape(function, capacity, capacity)
    price = (
        base + amplitude * _shape(function, distance, capacity)
        if inventory < i0
        else base - amplitude * _shape(function, distance, capacity)
    )
    return max(1, int(round(price)))


def projected_prices(
    inventory: Mapping[str, int],
    shops: tuple[str, ...],
    step: int,
    remaining_turns: int,
    *,
    shop_interval: int = 4,
    center_interval: int = 24,
) -> dict[str, int]:
    """Project official town consumption only; player trades are intentionally excluded."""
    projected = {item: int(inventory.get(item, MARKET_I0)) for item in PRODUCTS}
    for future in range(step, step + max(0, remaining_turns)):
        if future % shop_interval == 0:
            for shop in shops:
                for item in SHOPS.get(shop, ()):
                    projected[item] -= 2 if len(SHOPS[shop]) == 1 else 1
        if future % center_interval == 0:
            for item in PRODUCTS[:-1]:
                projected[item] -= 1
    return {item: market_price(item, amount) for item, amount in projected.items()}


def marginal_sale_values(
    item: str,
    inventory: int,
    quantity: int,
    *,
    overrides: Mapping[str, Mapping[str, object]] | None = None,
    opponent_buffer: int = 0,
) -> tuple[int, ...]:
    """Return the official quote for each unit sold, including market pressure.

    The environment increases market inventory after every successful sale.  A
    conservative buffer models a simultaneous opponent selling the same item.
    """
    if quantity <= 0:
        return ()
    start = max(0, inventory + opponent_buffer)
    return tuple(market_price(item, start + offset, overrides) for offset in range(quantity))


def marginal_buy_costs(
    item: str,
    inventory: int,
    quantity: int,
    *,
    overrides: Mapping[str, Mapping[str, object]] | None = None,
    opponent_buffer: int = 0,
) -> tuple[int, ...]:
    """Return the official post-buy quote for each unit purchased."""
    if quantity <= 0:
        return ()
    start = max(0, inventory - opponent_buffer)
    return tuple(market_price(item, start - offset - 1, overrides) for offset in range(quantity))


def _shape(function: str, value: float, capacity: float) -> float:
    value = max(0.0, value)
    if function == "linear":
        return value
    if function == "sq":
        return value * value
    if function == "sqrt":
        return math.sqrt(value)
    if function == "log":
        return math.log(1 + value)
    if function == "log10":
        return math.log10(1 + value)
    if function == "hinge":
        ratio = value / capacity if capacity > 0 else value
        return ratio + 8 * max(0.0, ratio - 1) ** 2
    return value


def _integer(value: object | None, default: int) -> int:
    return int(value) if isinstance(value, int | float | str) else default


def _number(value: object | None, default: float) -> float:
    return float(value) if isinstance(value, int | float | str) else default
