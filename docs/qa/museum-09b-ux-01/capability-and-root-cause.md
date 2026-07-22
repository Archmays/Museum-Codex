# MUSEUM-09B-UX-01 capability and root-cause review

## Evidence reviewed

The review covered the immutable 1.5.0 release projections (`layout.json`, `graph-summary.json`, `relationships.json`, `contexts.json`, and `artists.json`), the constellation route and its graph renderer/model/scale/detail/CSS layers, the artist-gallery route and copy layer, the M09B expansion builder, dossier and overview provenance, and the existing browser, screenshot, accessibility, and performance evidence.

## Root cause

The underlying 62 artists, 60 formal C-level relationships, contexts, Claim → Evidence → Source chains, media states, rights, and withdrawal records were correct. The visitor problem was a projection and information-architecture failure: `layout.json` encoded all artists into a global circular presentation, and the route treated “show everything” as the default graph task. Scale limiting could reduce the set, but it could not explain where to begin, why two people were connected, or what the relationship did not mean. Sigma/WebGL also made the graphical path structurally different from low-bandwidth, compact, and forced-colors paths. Label collision, visual centrality, and unexplained edges therefore remained visitor-facing even when the data itself was valid.

This could not be repaired with spacing, color, or label offsets alone. The default task, state model, URL/history behavior, graph projection, and accessible interaction model all had to change.

## Release projection changes

- Added immutable successor `release:art-expansion-batch-01-1.5.1`; 1.5.0 remains byte-identical.
- Added `relationship-explorer-config.json`: zero default nodes, no more than 9 rotating starters, focus initial limit 13 (center plus at most 12 neighbors), expanded limit 20, per-lane limit 4, and theme visual limit 16.
- Added 62 bilingual `public_intro`, `look_for`, `evidence_boundary`, and sentence-level Claim → Evidence → Source mappings without changing formal entities.
- Added successor-specific schemas so the schemas consumed by immutable 1.5.0 did not change.

## UI changes

- Start state: zero graph nodes, artist search, and a small coverage-balanced starter set.
- Focus state: one central artist with subject/material/technique lanes; every formal connection has a keyboard-operable “Why connected?” explanation and evidence entry.
- Theme state: one theme heading and a bounded visual set; the complete artist list remains available as text.
- List and relationship-table modes preserve complete discovery/audit, while Paths preserves A–B route tasks.
- DOM cards plus SVG relationship hit targets replace the default Sigma/WebGL dependency. Low-bandwidth, forced-colors, reduced-motion, keyboard, and screen-reader paths retain the same task.

## Preserved evidence boundary

Only the 60 released formal relationships are projected. Computational similarity never creates an edge; visual distance, size, and position do not express value or historical influence; evidence confidence remains textual and separate from historical relationship strength. Technical governance, source, rights, limits, and withdrawal details remain intact in secondary evidence layers rather than occupying the child-facing opening.

Conclusion: data correctness was preserved; the incorrect global-circle projection and visitor task were replaced at the release and UI architecture layers.
