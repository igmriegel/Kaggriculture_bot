"""Safety checks at the submission boundary."""

from typing import Any

from agent.core.contracts import Action

FARMER_OPS = {
    "NORTH",
    "SOUTH",
    "EAST",
    "WEST",
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


def validate_action(raw: Any) -> tuple[Action, str | None]:
    """Return a safe action and a reason when the input required fallback."""
    try:
        action = Action.model_validate(raw)
        if not action.farmer or not isinstance(action.farmer[0], str):
            raise ValueError("farmer action must begin with an operation")
        if action.farmer[0] not in FARMER_OPS:
            raise ValueError(f"unknown farmer operation: {action.farmer[0]}")
        for order in action.market:
            if not order or not isinstance(order[0], str) or order[0] not in MARKET_OPS:
                raise ValueError("unknown market operation")
        return action, None
    except Exception as exc:
        return Action.pass_action(), f"{type(exc).__name__}: {exc}"
