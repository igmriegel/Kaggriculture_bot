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
_ANIMAL_STRUCTURE = {"GOOSE": "COOP", "COW": "PASTURE", "SHEEP": "PASTURE"}


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
    seeds_raw = private.get("seeds")
    seeds: dict[str, Any] = seeds_raw if isinstance(seeds_raw, dict) else {}
    inventories_raw = private.get("inventories")
    inventories: list[dict[str, Any]] = (
        [entry for entry in inventories_raw if isinstance(entry, dict)]
        if isinstance(inventories_raw, list)
        else []
    )
    positions = [
        farm.get("farmer"),
        *(farm.get("hands") if isinstance(farm.get("hands"), list) else []),
    ]
    for index, command in enumerate([action.farmer, *action.hands]):
        position = positions[index] if index < len(positions) else None
        inventory = inventories[index] if index < len(inventories) else {}
        _validate_unit_legality(command, position, farm.get("tiles"), inventory, shed, seeds)
    for order in action.market:
        if order[0] == "SELL" and _positive_or_zero(shed.get(order[1])) < _positive(order[2]):
            raise ValueError("sell exceeds shed inventory")


def _validate_unit_legality(
    command: list[Any],
    position: Any,
    tiles: Any,
    inventory: dict[str, Any],
    shed: dict[str, Any],
    seeds: dict[str, Any],
) -> None:
    if not isinstance(position, list) or len(position) < 2:
        raise ValueError("unit has no official position")
    x, y = _positive_or_zero(position[0]), _positive_or_zero(position[1])
    if not isinstance(tiles, list) or not tiles or not isinstance(tiles[0], list):
        raise ValueError("missing board tiles")
    height, width = len(tiles), len(tiles[0])
    op = command[0]
    if op in MOVES:
        dx, dy = {"NORTH": (0, -1), "SOUTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0)}[op]
        if not 0 <= x + dx < width or not 0 <= y + dy < height:
            raise ValueError("move exits board")
        return
    tile = tiles[y][x] if y < height and x < len(tiles[y]) else "LOCKED"
    access = _shed_access(x, y, width)
    if op in {"DROP", "PICKUP"} and not access:
        raise ValueError("shed action requires shed access tile")
    if op == "PICKUP" and _positive_or_zero(shed.get(command[1])) < _quantity(command, 2):
        raise ValueError("pickup exceeds shed inventory")
    if op in {"DROP", "PICKUP", "PASS"}:
        return
    if tile == "LOCKED":
        raise ValueError("tile operation targets locked land")
    if op == "PLANT" and (tile is not None or _positive_or_zero(seeds.get(command[1])) < 1):
        raise ValueError("plant requires empty tile and seed")
    if op == "WATER" and not (
        isinstance(tile, dict) and tile.get("kind") == "PLANT" and not tile.get("watered_today")
    ):
        raise ValueError("water requires an unwatered plant")
    if op == "HARVEST" and not (
        isinstance(tile, dict) and _positive_or_zero(tile.get("yield_units")) > 0
    ):
        raise ValueError("harvest requires held yield")
    if op == "FERTILIZE" and (
        not isinstance(tile, dict)
        or tile.get("kind") != "PLANT"
        or _positive_or_zero(inventory.get("FERTILIZER")) < 1
    ):
        raise ValueError("fertilize requires plant and fertilizer")
    if op == "FEED" and (
        not isinstance(tile, dict)
        or not tile.get("animal")
        or tile.get("fed_today")
        or _positive_or_zero(inventory.get("WHEAT")) < 1
    ):
        raise ValueError("feed requires an unfed animal and wheat")
    if op == "CARE" and (
        not isinstance(tile, dict) or not tile.get("animal") or tile.get("cared_today")
    ):
        raise ValueError("care requires an uncared animal")
    if op == "COLLECT_FERTILIZER" and (
        not isinstance(tile, dict) or not tile.get("animal") or not tile.get("fertilizer_available")
    ):
        raise ValueError("collection requires available animal fertilizer")
    if op == "PLACE" and _positive_or_zero(inventory.get(command[1])) < 1:
        raise ValueError("place requires item in unit inventory")
    if (
        op == "PLACE"
        and command[1] in _ANIMALS
        and (
            not isinstance(tile, dict)
            or tile.get("kind") != _ANIMAL_STRUCTURE[command[1]]
            or tile.get("animal")
        )
    ):
        raise ValueError("animal placement requires matching empty structure")
    if op == "PLACE" and command[1] not in _ANIMALS and not access:
        raise ValueError("product placement requires shed access tile")
    if op in {"BUILD_COOP", "BUILD_PASTURE"} and tile is not None:
        raise ValueError("building requires an empty tile")
    if op == "DIG" and (tile is None or (isinstance(tile, dict) and tile.get("animal"))):
        raise ValueError("dig cannot remove an empty tile or animal")


def _shed_access(x: int, y: int, board_size: int) -> bool:
    half = board_size // 2
    return (x, y) in {(half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half)}


def _quantity(command: list[Any], index: int) -> int:
    return _positive(command[index]) if len(command) > index else 1


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
