# Kaggriculture reference mirror

This directory is an immutable, verbatim reference copy of the two advanced
Kaggriculture environment artifacts used by the project. It is evidence, not
project-owned implementation. Do not edit these files to express a project
decision; record decisions in `docs/architecture/` instead.

## Provenance

Imported: 2026-08-21.

Upstream: `kaggle-environments` 1.32.7; environment version 0.1.0.

| Mirrored file | Upstream source path | SHA-256 of upstream artifact |
|---|---|---|
| [`kaggriculture.py`](kaggriculture.py) | `kaggle_environments/envs/kaggriculture/kaggriculture.py` | `bc8a54879ef02c7ea64b8b333d6a976f0ea65c4949149d01f463f23bccee653e` |
| [`kaggriculture.json`](kaggriculture.json) | `kaggle_environments/envs/kaggriculture/kaggriculture.json` | `a82c89c1a2315b93f39775d8e025471a01b738647c9772658368ee6b1b6f4867` |

The source interpreter and schema are copied in full and retain their original
formatting. The provenance lives in this companion file so that the mirrored
JSON remains valid. When updating the mirror, copy both upstream artifacts,
recompute both checksums, update this table, and record any rule conflict in
the decision log.

## Authority order

1. The installed `kaggle-environments` implementation and Kaggle replay/log
   behavior are authoritative.
2. This mirror is the versioned local reference for that installed source.
3. Project documents describe design decisions and can never override the
   environment.
4. Local fixtures and reports are observed evidence; they can reveal a
   discrepancy but do not change the rule.
