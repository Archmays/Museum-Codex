# Schema contract

All schemas use JSON Schema Draft 2020-12. The current foundation set is version `1.0.0`; data records also carry `schema_version`, while each dataset release records the exact schema versions it consumed.

`schema-manifest.json` is the machine-readable dependency registry. Dependencies are direct: branch schemas extend a common schema; transitive dependencies are resolved through the referenced schema. A breaking meaning, required-field, or type change increments the schema major version. Compatible optional additions increment minor; clarifications and non-breaking corrections increment patch.

The canonical `$id` values are identifiers, not live network dependencies. Validation loads every schema from this repository and resolves `$ref` through the manifest-backed local registry, so offline checks are deterministic.

| Layer | Schemas | Dependency rule |
|---|---|---|
| common identity | `entity` | none |
| common governance | `relationship`, `claim`, `evidence`, `source`, `media-asset`, `dataset-release` | depend on reusable definitions in `entity` |
| release artifacts | `source-rules-snapshot`, `license-decision-registry`, `third-party-notices`, `attribution-manifest` | validate the actual hashed files shipped beside release data |
| art | `artist`, `artwork`, `artist-relationship` | extend `entity` or `relationship` |
| pipeline | `adapter-contract`, `acquisition-request`, `raw-snapshot-manifest`, `field-provenance`, `normalized-candidate`, `identity-proposal`, `merge-record`, `review-decision`, `pipeline-run`, `review-bundle` | build-time acquisition and local review only; never public release data |
| biology | `taxon`, `ecosystem-interaction` | extend `entity` or `relationship` |

Run `python scripts/validate_governance_foundation.py` after any schema or manifest change. Update the corresponding positive/negative fixtures and tests in the same change.

The validator, not the input record, dispatches canonical schemas: `artist`, `artwork`, art relationships, taxa, and biology interactions cannot downgrade to a common base schema. Source rules carry stable IDs, executable normalized scope matchers, and snapshot hashes; publishable consumers bind the exact rule, content class, actual scope locator, and direct-vs-object permission resolution they used. `schema_versions` is recomputed from concrete records and artifact schemas. A physical release is accepted only when its declared and actual file sets, artifact contents, self-hosted media bytes, IDs, hashes, and governance registries close exactly.

Pipeline records are dispatched by `entity_type` and typed ID prefix through `museum_pipeline.validation.dispatch`; a record-provided schema path is never trusted. Pipeline candidate, raw, intermediate, merge, and review records are non-release artifacts and are blocked from `dist` and Pages independently of schema validity.
