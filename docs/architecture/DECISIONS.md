# Decisions

| ID | Decision | Status |
|---|---|---|
| D-001 | Target the advanced `kaggriculture` environment. | accepted |
| D-002 | Prioritize harness evidence before strategy expansion. | accepted |
| D-003 | Preserve unknown observation fields until verified fixtures exist. | accepted |
| D-004 | Expose harness through a stable facade and explicit registries. | accepted |
| D-005 | Persist summaries as JSON and turn events as JSONL. | accepted |
| D-006 | Normalize only observed fields and degrade unknown V1 mechanics to safe PASS. | accepted |
| D-007 | Promote V1 operationally only after fixed scenario and isolated-package evidence. | accepted |
| D-008 | Keep a verbatim, checksummed mirror of the installed official Kaggriculture interpreter and schema; on conflict, installed/replay behavior wins. | accepted |
| D-009 | Treat contracts, fixtures, and observed evidence as separate layers: unknown fields remain permissive, while engines consume normalized state only. | accepted |
| D-010 | Sanitize independently invalid unit and market commands at the submission boundary so one rejected command cannot discard unrelated legal work. | accepted |
| D-011 | Keep `leader-v3` isolated from the V2 submission candidate until matching development and confirmation matrices demonstrate non-regression in money, worst quartile, and win rate. | accepted |
