"""Forward state simulator and lookahead evaluator for strategy engines."""

from __future__ import annotations

from dataclasses import replace

from agent.core.state import NormalizedState
from agent.domain.economics import CROP_BASE_PRICES


def evaluate_state_value(state: NormalizedState, config: Any | None = None) -> float:
    """Evaluate a heuristic scalar value for a given NormalizedState using engine parameters."""
    # Financial liquidity
    score = float(state.money)

    # Config-based crop valuation multipliers
    melon_mult = getattr(config, "melon_roi_multiplier", 1.75) if config else 1.75
    strawberry_mult = getattr(config, "strawberry_roi_multiplier", 1.52) if config else 1.52

    # Shed inventory expected liquidity with marginal price floors
    floor = getattr(config, "marginal_sale_price_ratio_floor", 0.45) if config else 0.45
    for item, qty in state.shed.items():
        base_p = CROP_BASE_PRICES.get(item, state.prices.get(item, 10.0))
        mult = 1.0
        if item == "MELON":
            mult = melon_mult
        elif item == "STRAWBERRY":
            mult = strawberry_mult
        score += qty * base_p * mult

    # Seed stock value
    for seed, qty in state.seeds.items():
        score += qty * 15.0

    # Field assets and expected growth value
    days_left = max(0, 30 - state.day)
    for tile in state.tiles:
        if tile.kind == "PLANT":
            score += 20.0  # Base land value
            if tile.crop:
                base_val = CROP_BASE_PRICES.get(tile.crop, 30.0)
                crop_mult = (
                    melon_mult
                    if tile.crop == "MELON"
                    else (strawberry_mult if tile.crop == "STRAWBERRY" else 1.0)
                )
                if tile.yield_units > 0:
                    score += tile.yield_units * base_val * crop_mult
                elif days_left >= 3:
                    score += base_val * 0.5 * crop_mult
        elif tile.kind == "LIVESTOCK":
            score += 350.0  # Animal capital value

    # Time & productivity bonus
    score -= state.day * 2.0  # Encourage early accumulation

    return score


class ForwardSimulator:
    """Simulates 1-step outcome of basic farmer actions on NormalizedState."""

    @staticmethod
    def step_action(state: NormalizedState, action: tuple[str, ...]) -> NormalizedState:
        """Simulate the immediate state change of a farmer unit action."""
        if not action or action[0] == "PASS":
            return state

        cmd = action[0].upper()
        x, y = state.position
        tiles = list(state.tiles)
        tile_map = {(t.x, t.y): t for t in tiles}
        current_tile = tile_map.get((x, y))

        new_x, new_y = x, y
        if cmd == "NORTH":
            new_y = max(0, y - 1)
        elif cmd == "SOUTH":
            new_y = min(state.board_size - 1, y + 1)
        elif cmd == "WEST":
            new_x = max(0, x - 1)
        elif cmd == "EAST":
            new_x = min(state.board_size - 1, x + 1)

        new_money = state.money
        new_seeds = dict(state.seeds)
        new_shed = dict(state.shed)

        if cmd in ("NORTH", "SOUTH", "EAST", "WEST"):
            return replace(state, position=(new_x, new_y))

        if cmd == "WATER" and current_tile and current_tile.kind == "PLANT":
            updated_tile = replace(current_tile, watered_today=True)
            new_tiles = [updated_tile if (t.x, t.y) == (x, y) else t for t in tiles]
            return replace(state, tiles=tuple(new_tiles))

        if cmd == "HARVEST" and current_tile and current_tile.yield_units > 0:
            crop = current_tile.crop or "WHEAT"
            qty = current_tile.yield_units
            new_shed[crop] = new_shed.get(crop, 0) + qty
            updated_tile = replace(current_tile, yield_units=0, crop=None)
            new_tiles = [updated_tile if (t.x, t.y) == (x, y) else t for t in tiles]
            return replace(state, shed=new_shed, tiles=tuple(new_tiles))

        if cmd == "PLANT" and len(action) > 1 and current_tile and current_tile.kind == "PLANT":
            crop_to_plant = action[1]
            if new_seeds.get(crop_to_plant, 0) > 0:
                new_seeds[crop_to_plant] -= 1
                updated_tile = replace(current_tile, crop=crop_to_plant, planted_day=state.day)
                new_tiles = [updated_tile if (t.x, t.y) == (x, y) else t for t in tiles]
                return replace(state, seeds=new_seeds, tiles=tuple(new_tiles))

        return state
