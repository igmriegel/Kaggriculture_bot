# MVP heuristic

The first engine is intentionally conservative. It protects the farm before it
optimizes the market: water an existing plant, harvest available yield, plant
wheat when a seed is available, buy one wheat seed at the beginning of a turn
day when affordable, then move toward the first empty unlocked tile.

```mermaid
flowchart TD
    O[Observation] --> P{Current tile is a plant?}
    P -- yes --> W{Watered today?}
    W -- no --> WATER[WATER]
    W -- yes --> Y{Harvestable yield?}
    Y -- yes --> HARVEST[HARVEST]
    Y -- no --> E{Empty unlocked tile and wheat seed?}
    P -- no --> E
    E -- yes --> PLANT[PLANT WHEAT]
    E -- no --> B{Hour is 0 and money >= 10?}
    B -- yes --> BUY[BUY_SEED WHEAT 1 + PASS]
    B -- no --> MOVE[Move toward empty tile or PASS]
```

This policy is a baseline, not a claim of competitiveness. Promotion requires
reproducible benchmark evidence against configured opponents and seeds.
