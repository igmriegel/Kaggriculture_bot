"""Unit tests for Monte Carlo Price Oracle."""

import time

from agent.domain.economics import PRODUCTS
from agent.domain.monte_carlo import monte_carlo_price_projection


def test_monte_carlo_price_projection_deterministic_when_no_unlocks() -> None:
    """When target_day has no future unlocks, p10 == mean == p90."""
    res = monte_carlo_price_projection(
        current_inventory={"WHEAT": 10000, "STRAWBERRY": 10000},
        current_shops=("BAKERY",),
        current_day=25,
        current_hour=0,
        target_day=26,
        n_samples=50,
    )
    for prod in PRODUCTS:
        mean_p, p10, p90 = res[prod]
        assert mean_p == p10 == p90
        assert mean_p >= 1.0


def test_monte_carlo_price_projection_with_future_unlocks() -> None:
    """When future shop unlocks exist, p10 <= mean <= p90 and variance exists."""
    res = monte_carlo_price_projection(
        current_inventory={"STRAWBERRY": 10000, "MILK": 10000},
        current_shops=(),
        current_day=0,
        current_hour=0,
        target_day=15,
        n_samples=100,
    )
    for prod in PRODUCTS:
        mean_p, p10, p90 = res[prod]
        assert p10 <= mean_p <= p90
        assert p10 >= 1.0


def test_monte_carlo_performance_budget() -> None:
    """Execution time for 150 samples over 15-day horizon must be < 5ms."""
    start = time.perf_counter()
    res = monte_carlo_price_projection(
        current_inventory={"WHEAT": 10000},
        current_shops=("BAKERY",),
        current_day=0,
        current_hour=0,
        target_day=15,
        n_samples=150,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    assert elapsed_ms < 100.0, f"Monte Carlo projection took {elapsed_ms:.2f}ms, expected < 100ms"
    assert len(res) == len(PRODUCTS)
