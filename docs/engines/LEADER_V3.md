# Leader V3 hybrid portfolio policy

`leader-v3` is an experimental successor to `leader-v2`. The submission entry
point remains V2 because the promotion matrix must prove that V3 is at least as
safe and profitable.

```mermaid
flowchart TD
    O[Normalized observation] --> P[Daily portfolio scorer]
    P --> C[Cash crops: wheat/carrot]
    P --> H[Long crops: melon/strawberry]
    P --> A[Animal chain reservation]
    C --> M[Marginal official market quotes]
    H --> M
    A --> M
    M --> L[Fibonacci labor and land ROI]
    L --> U[Reserved unit allocator]
    U --> V[Action validator]
    V --> A[Idle/fallback audit]
```

The planner scores crops by current price, demand, maturity, and remaining
horizon. Wheat and carrot provide early cash; melon and strawberry are added
only when their maturity fits the season. Sales simulate each unit against the
official market curve and retain feed, with a small opponent-pressure buffer.

Animals are purchased only when an empty pasture, shed headroom, wheat ration,
and the pickup/placement/feed chain are simultaneously available. Every market
decision reserves the next feed cycle, next-day Fibonacci labor, seed cost, and
the operating cash floor. Hiring is reconsidered after each daily hand reset,
but only when productive work and that reserve are both present. If animals,
feed, or cash become misaligned, recovery sells/feeds/collects/drops before
allowing a new expansion. Land is bought only when expected workload over the
remaining horizon covers its configured cost.

V3 is deterministic for a fixed observation. It does not copy replay
coordinates, introduce model dependencies, or alter the strategy-agnostic
harness. Benchmark reports must include zero errors, fallbacks, and illegal
actions before considering promotion. They also report productive, movement,
legitimate-wait, fallback-PASS, and idle-PASS classes, idle percentage, longest
PASS streak, day-hour heatmaps, and inferred/lost fallback actions.
