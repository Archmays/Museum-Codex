# MUSEUM-03B relationship research policy

## Scope and candidate closure

Relationship research starts from all 45 MUSEUM-03A leads. Every lead receives exactly one disposition: `promoted_to_formal_relationship`, `retained_for_more_evidence`, `rejected`, `superseded`, or `out_of_scope`. Tracked closure stores opaque lead IDs, hashes, decisions, and public-safe rationales; it does not expose unapproved alternate candidates or private review notes.

The research set must contain 50–80 deliberate candidates. The formal reviewed target is 36–60 and the MUSEUM-04 recommendation floor is 30. Every approved primary artist needs at least two distinct explainable edges or a reviewed exception. Counts never override evidence quality.

## Controlled semantics

Only the controlled relationship types in `schemas/art/artist-relationship.schema.json` are allowed. `related_to`, popularity/market relations, inferred influence, visual-nearness-as-history, and `computationally_similar_to` are forbidden. `computational_similarity` remains null for every MUSEUM-03B formal relationship.

### Level A

Level A is directional historical evidence: named teacher/student, documented studio work, collaboration, direct quotation/reference, or explicit influence language in an appropriate exact source. A comparison, shared label, or chronological overlap cannot become A.

### Level B

Level B requires a sourced typed movement, group, institution, exhibition, patron, or place/time context. The context and relevant temporal/place scopes must close. The wording must not imply contact or influence.

### Level C

Level C is an explicit curatorial comparison bound to a sourced subject, material, technique, or genuine scholarly-comparison context. Each edge states its educational question. Shared metadata does not trigger automatic all-pairs generation, and causal language is forbidden.

## Evidence and review

Each formal edge closes Relationship → Claim → Evidence → Source, with exact object/manual locators, source-license bindings, uncertainty, counters where present, and separate relationship/data review sign-offs. Historical strength, evidence confidence, computational similarity, and curatorial relevance remain separate fields.

Symmetric edges use one canonical endpoint order. Self-links, duplicate inverses, missing endpoints/contexts, implicit influence, and orphaned references are hard failures.

## Phase boundary

Formal relationships are internal reviewed graph input only. They are not displayed on Pages and do not authorize MUSEUM-04.
