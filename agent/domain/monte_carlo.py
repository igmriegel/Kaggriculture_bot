"""Monte Carlo Price Oracle for market projections under shop unlock uncertainty."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from agent.domain.economics import MARKET_I0, PRODUCTS, SHOPS, market_price

SHOP_NAMES = sorted(SHOPS.keys())
SHOP_UNLOCK_DAYS = (3, 6, 9, 12, 15, 18, 21, 24)


def _count_multiples(k: int, start: int, end: int) -> int:
    """Return count of multiples of k in step range [start, end)."""
    if end <= start:
        return 0
    return ((end - 1) // k) - ((start - 1) // k)


def _analytical_drain(
    current_inventory: Mapping[str, int],
    current_shops: tuple[str, ...],
    current_day: int,
    current_hour: int,
    target_day: int,
    extra_shops_schedule: list[tuple[int, str]] | None = None,
) -> dict[str, int]:
    """Analytical O(1) exact projection of market inventory drain."""
    projected = {item: int(current_inventory.get(item, MARKET_I0)) for item in PRODUCTS}
    start_step = current_day * 24 + current_hour
    target_step = target_day * 24

    if target_step <= start_step:
        return projected

    # 1. Town center consumption
    center_ticks = _count_multiples(24, start_step, target_step)
    if center_ticks > 0:
        for item in PRODUCTS[:-1]:  # Exclude FERTILIZER
            projected[item] -= center_ticks

    # 2. Existing active shops
    shop_ticks = _count_multiples(4, start_step, target_step)
    if shop_ticks > 0:
        for shop in current_shops:
            items = SHOPS.get(shop, ())
            decrement = 2 if len(items) == 1 else 1
            for item in items:
                projected[item] -= shop_ticks * decrement

    # 3. Extra future shops
    if extra_shops_schedule:
        for unlock_day, shop_name in extra_shops_schedule:
            shop_start = max(start_step, unlock_day * 24)
            ticks = _count_multiples(4, shop_start, target_step)
            if ticks > 0:
                items = SHOPS.get(shop_name, ())
                decrement = 2 if len(items) == 1 else 1
                for item in items:
                    projected[item] -= ticks * decrement

    return projected


def monte_carlo_price_projection(
    current_inventory: Mapping[str, int],
    current_shops: tuple[str, ...],
    current_day: int,
    current_hour: int,
    target_day: int,
    *,
    n_samples: int = 150,
    seed: int = 42,
) -> dict[str, tuple[float, float, float]]:
    """Project market prices at target_day under shop unlock uncertainty.

    Returns dict mapping product -> (mean_price, p10_price, p90_price).
    Uses ultra-fast closed-form analytical drain (< 1ms total runtime).
    """
    future_unlock_days = [d for d in SHOP_UNLOCK_DAYS if current_day < d <= target_day]
    n_future = len(future_unlock_days)

    if n_future == 0 or n_samples <= 0:
        projected = _analytical_drain(
            current_inventory, current_shops, current_day, current_hour, target_day
        )
        prices = {item: market_price(item, inv) for item, inv in projected.items()}
        return {item: (float(p), float(p), float(p)) for item, p in prices.items()}

    rng = np.random.default_rng(seed)
    shop_indices = rng.integers(0, len(SHOP_NAMES), size=(n_samples, n_future))

    price_matrix = np.zeros((n_samples, len(PRODUCTS)), dtype=np.float32)

    for s in range(n_samples):
        extra_schedule = [
            (future_unlock_days[i], SHOP_NAMES[shop_indices[s, i]]) for i in range(n_future)
        ]
        projected = _analytical_drain(
            current_inventory,
            current_shops,
            current_day,
            current_hour,
            target_day,
            extra_shops_schedule=extra_schedule,
        )

        for i, item in enumerate(PRODUCTS):
            price_matrix[s, i] = market_price(item, projected.get(item, MARKET_I0))

    result: dict[str, tuple[float, float, float]] = {}
    for i, item in enumerate(PRODUCTS):
        prices = price_matrix[:, i]
        result[item] = (
            float(np.mean(prices)),
            float(np.percentile(prices, 10)),
            float(np.percentile(prices, 90)),
        )

    return result
