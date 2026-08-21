# Harness contract

## Responsibilities

- Create and run deterministic episodes through an `EnvironmentAdapter`.
- Validate candidate actions and substitute `PASS` while recording the reason.
- Classify normal completion, agent errors, environment errors, timeouts, and
  safety-limit termination.
- Emit versioned JSON episode/benchmark summaries and optional JSONL turn events.
- Resolve adapters, agents, reporters, and scenarios through explicit registries.

## Boundaries

- `agent.core` owns game protocol models and validation.
- `agent.harness` owns execution and evidence.
- `agent.engines` returns candidate actions only.
- `main.py` remains the competition entry point; it does not own harness logic.

## Compatibility

The public facade is the compatibility boundary. New model fields are optional
and defaulted; artifact schema changes require a schema-version increment.
Internal module rearrangement is allowed if facade imports, registry names, and
artifact versions remain compatible.

## Verified Kaggriculture wire contract

The following shapes are verified against the mirrored advanced environment
([source](../reference/kaggriculture/README.md)). They are the target for
normalized contracts and fixtures; the present implementation may intentionally
cover only the entries marked as gaps in the implementation map.

```text
action = {
  "farmer": [operation, ...arguments],
  "hands": [[operation, ...arguments], ...],   # official hand order
  "market": [[operation, ...arguments], ...],  # official order, capped per turn
}

observation = {
  "player": player_id,
  "farms": [public_farm_by_player, ...],
  "private": {"shed": inventory, "seeds": inventory,
              "inventories": [farmer_inventory, hand_inventory, ...]},
  "market": {"inventory": inventory, "prices": prices},
  "town": {"unlocked_shops": [...]},
  "day": day,
  "hour": hour,
}
```

A public farm exposes the tile grid, money, farmer position, ordered hand
positions, unlocked quadrants, and the day’s hire count. It must not expose an
opponent’s shed or per-unit inventory. Tiles are `null` (empty), `"LOCKED"`,
or objects representing a `WEED`, plant, empty `COOP`/`PASTURE`, or an animal
occupying one of those structures.

The normalized action contract must always emit a farmer action, an ordered
hand action for each observed hand (or a recorded safe fallback), and ordered
market actions. Unknown observation fields remain permissive at the boundary,
but strategy code must consume normalized models only and must never inspect
the raw observation dictionary directly.
