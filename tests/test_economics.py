from agent.domain.economics import MARKET_I0, market_price, projected_prices


def test_market_price_is_base_at_target_inventory() -> None:
    assert market_price("WHEAT", MARKET_I0) == 25


def test_town_projection_increases_price_for_consumed_product() -> None:
    prices = projected_prices({"WHEAT": MARKET_I0}, ("BAKERY",), 0, 4)
    assert prices["WHEAT"] > 25
