"""Legality checks for the verified Kaggriculture command surface.

The environment still makes the final decision.  Supplying an observation turns
this into a stricter pre-flight check; without one it remains a schema guard for
the generic harness.
"""

from typing import Any

from agent.core.contracts import Action

MOVES = {"NORTH", "SOUTH", "EAST", "WEST"}
UNIT_OPS = MOVES | {
    "PASS",
    "PICKUP",
    "PLACE",
    "DROP",
    "PLANT",
    "WATER",
    "HARVEST",
    "FERTILIZE",
    "BUILD_COOP",
    "BUILD_PASTURE",
    "FEED",
    "COLLECT_FERTILIZER",
    "CARE",
    "DIG",
}
MARKET_OPS = {"BUY_SEED", "BUY_ANIMAL", "BUY_PRODUCT", "SELL", "HIRE", "BUY_LAND"}
_CROPS = {"WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"}
_ANIMALS = {"GOOSE", "COW", "SHEEP"}
_PRODUCTS = _CROPS | {"EGG", "MILK", "WOOL", "FERTILIZER"}


def validate_action(
    raw: Any, observation: dict[str, Any] | None = None
) -> tuple[Action, str | None]:
    """Return a safe command, rejecting impossible unit count, stock, and orders."""
    try:
        action = Action.model_validate(raw)
        units = [action.farmer, *action.hands]
        for command in units:
            _validate_unit(command)
        for order in action.market:
            _validate_order(order)
        if observation is not None:
            _validate_against_observation(action, observation)
        return action, None
    except Exception as exc:
        return Action.pass_action(), f"{type(exc).__name__}: {exc}"


def _validate_unit(command: list[Any]) -> None:
    if not command or not isinstance(command[0], str) or command[0] not in UNIT_OPS:
        raise ValueError("unknown unit operation")
    op = command[0]
    if op in {"PLANT", "PICKUP", "PLACE"} and (len(command) < 2 or not isinstance(command[1], str)):
        raise ValueError(f"{op} requires an item")
    if op == "PLANT" and command[1] not in _CROPS:
        raise ValueError("unknown crop")
    if op == "PLACE" and command[1] not in _ANIMALS | _PRODUCTS:
        raise ValueError("unknown placement item")


def _validate_order(order: list[Any]) -> None:
    if not order or not isinstance(order[0], str) or order[0] not in MARKET_OPS:
        raise ValueError("unknown market operation")
    if order[0] in {"HIRE", "BUY_LAND"}:
        return
    if len(order) < 3 or not isinstance(order[1], str) or _positive(order[2]) <= 0:
        raise ValueError("market order requires a positive quantity")
    item = order[1]
    if order[0] == "BUY_SEED" and item not in _CROPS:
        raise ValueError("unknown seed")
    if order[0] == "BUY_ANIMAL" and item not in _ANIMALS:
        raise ValueError("unknown animal")
    if order[0] in {"BUY_PRODUCT", "SELL"} and item not in _PRODUCTS:
        raise ValueError("unknown product")


def _validate_against_observation(action: Action, observation: dict[str, Any]) -> None:
    farms = observation.get("farms")
    player = _positive_or_zero(observation.get("player"))
    if not isinstance(farms, list) or player >= len(farms) or not isinstance(farms[player], dict):
        raise ValueError("missing player farm")
    farm = farms[player]
    hands = farm.get("hands", [])
    if not isinstance(hands, list) or len(action.hands) > len(hands):
        raise ValueError("action addresses a non-existent hand")
    limit = _positive_or_zero(observation.get("maxMarketOrdersPerTurn"))
    if not limit:
        limit = 10
    if len(action.market) > limit:
        raise ValueError("market order limit exceeded")
    private_raw = observation.get("private")
    private: dict[str, Any] = private_raw if isinstance(private_raw, dict) else {}
    shed_raw = private.get("shed")
    shed: dict[str, Any] = shed_raw if isinstance(shed_raw, dict) else {}
    for order in action.market:
        if order[0] == "SELL" and _positive_or_zero(shed.get(order[1])) < _positive(order[2]):
            raise ValueError("sell exceeds shed inventory")


def _positive(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("quantity must be an integer") from exc


def _positive_or_zero(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0
