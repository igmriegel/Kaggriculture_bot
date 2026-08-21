# MVP heuristic

The baseline protects plants first, harvests available yield, plants wheat when
possible, buys a wheat seed at day start, and otherwise moves toward an empty
tile. It returns a candidate action only; harness validation remains mandatory.

```mermaid
flowchart TD
    O[Observation] --> P{Plant on current tile?}
    P -- unwatered --> W[WATER]
    P -- yield available --> H[HARVEST]
    P --> S{Wheat seed and empty tile?}
    S -- yes --> PL[PLANT WHEAT]
    S -- no --> B{New day and affordable?}
    B -- yes --> BUY[BUY_SEED + PASS]
    B -- no --> M[Move or PASS]
```
