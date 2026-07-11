# Data zones

The public site must consume only immutable files produced under `data/releases/<dataset-version>/` in a later phase.

| Zone | Purpose | Git policy | Mutability |
|---|---|---|---|
| `raw/` | timestamped byte-for-byte source snapshots plus request metadata | ignored; store externally or with an approved large-file strategy | append-only |
| `intermediate/` | normalized, deduplicated, unresolved and conflict-preserving work products | ignored | rebuildable |
| `reviewed/` | human-reviewed candidate records and review logs | versioned when introduced | changes require review history |
| `releases/` | manifest-led static JSON/GeoJSON and derived search indexes | versioned | immutable; replace by new version |

Each release manifest records source snapshot timestamps, content hashes, schema versions, build version, included IDs, withdrawals, and predecessor. Secrets and downloaded media never belong in these directories.

A future physical release directory is closed: its actual files must equal `manifest.json` plus every declared manifest path. It carries hashed source-rule and license-decision snapshots, parsed third-party notices and attribution manifests, and exactly one byte file for every `self_hosted` media record. Media bytes are admitted only when their SHA-256 equals the record `content_hash`; undeclared files and broken parent/derivation chains fail the build.
