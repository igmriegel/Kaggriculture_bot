# Decisions and technical debt

Open a new entry when an assumption affects a contract, dependency, benchmark,
or submission behavior.

## D-001 — Advanced competition target

- **Decision:** target `kaggriculture`, not `kaggriculture_beginner`.
- **Evidence:** the official advanced README exposes market, town, private
  inventory, animals, land, and the 720-turn season.
- **Impact:** the adapter must preserve advanced `farmer` and `market` actions.
- **Status:** accepted.

## D-002 — Harness before strategy expansion

- **Decision:** prioritize a reliable local harness, then expand the heuristic,
  then evaluate data-driven or RL policies.
- **Reason:** invalid actions, incomplete episodes, and unreproducible seeds
  make strategy comparisons unreliable.
- **Status:** accepted.

## D-003 — Provisional Pydantic observation model

- **Decision:** model verified top-level fields and preserve unknown fields with
  `extra="allow"`.
- **Reason:** the official environment is the source of truth and the adapter is
  not yet implemented.
- **Debt:** add nested typed models after collecting official fixtures.
- **Next action:** implement the official adapter and freeze representative fixtures.
