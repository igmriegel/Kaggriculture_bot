# Graphify knowledge graph

Graphify is a local development tool, not a submission dependency. It maps the
repository into a queryable structural graph under `graphify-out/`; generated
artifacts are ignored by Git and must never enter a Kaggle submission package.

## Commands

```bash
# Build structural code graph without an LLM key.
graphify . --code-only --no-viz

# Rebuild after code changes.
graphify . --code-only --no-viz --update

# Query relationships in the existing graph.
graphify query "What calls EpisodeRunner?" --budget 800
graphify path "EpisodeRunner" "KaggleEnvironmentAdapter"
graphify explain "RunConfig"
```

## Document enrichment

The full graph also extracts semantic relationships from Markdown and other
documents. The installed Graphify version requires an explicitly configured LLM
backend/key for that step. Do not add a key to this repository. Use the
code-only graph by default; enable document enrichment only in a trusted local
environment with the appropriate secret-management policy.

## Agent workflow

When `graphify-out/graph.json` exists, use Graphify before broad repository
searches for architecture, symbol-relationship, and data-flow questions. Run an
incremental rebuild after structural code changes, then query the graph rather
than treating the generated files as source of truth.
