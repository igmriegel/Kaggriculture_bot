from agent.domain.economics import marginal_buy_costs, marginal_sale_values
from agent.engines.leader_v3 import LeaderV3Engine
from agent.harness import registry
from agent.harness.builtins import register_builtins
from tests.test_leader_v2 import _observation


def _empty_board() -> list[list[object]]:
    return [[None if x < 5 and y < 5 else "LOCKED" for x in range(10)] for y in range(10)]


def test_v3_does_not_copy_the_v2_fixed_opening() -> None:
    action = LeaderV3Engine().act(_observation(tiles=_empty_board(), hour=1))

    assert action["market"] != [
        ["HIRE"],
        ["HIRE"],
        ["HIRE"],
        ["HIRE"],
        ["HIRE"],
        ["BUY_ANIMAL", "SHEEP", 2],
        ["BUY_ANIMAL", "COW", 2],
        ["BUY_SEED", "MELON", 11],
        ["BUY_SEED", "WHEAT", 6],
        ["BUY_PRODUCT", "WHEAT", 4],
    ]


def test_v3_reserves_feed_chain_before_buying_animal() -> None:
    tiles = _empty_board()
    tiles[0][0] = {"kind": "PASTURE"}
    observation = _observation(
        tiles=tiles,
        day=3,
        hour=1,
        private={"shed": {}, "seeds": {}, "inventories": [{}]},
    )

    action = LeaderV3Engine().act(observation)

    product_index = next(i for i, order in enumerate(action["market"]) if order[0] == "BUY_PRODUCT")
    animal_index = next(i for i, order in enumerate(action["market"]) if order[0] == "BUY_ANIMAL")
    assert action["market"][product_index][1] == "WHEAT"
    assert product_index < animal_index


def test_marginal_quotes_follow_the_official_market_curve() -> None:
    sale = marginal_sale_values("MELON", 10_000, 3, opponent_buffer=2)
    buy = marginal_buy_costs("WHEAT", 10_000, 3, opponent_buffer=2)

    assert len(sale) == len(buy) == 3
    assert sale[0] >= sale[-1]
    assert buy[0] <= buy[-1]


def test_v3_is_registered_without_promoting_submission_entrypoint() -> None:
    register_builtins()

    assert "leader-v3" in registry.agents.names()
    assert "leader-v3-pass-development" in registry.scenarios.names()
