# Museum-Codex project rules

These rules apply to all work in this repository.

## Phase and product boundary

- Read the current phase report, entry criteria, relevant policy, and schema before changing a phase artifact.
- `MUSEUM-00` is a governance foundation, not a product implementation. Do not describe planned UI as shipped.
- Do not enter the next phase without the user authorizing it. GitHub Pages remains disabled until a later phase.
- Preserve reviewed and released data. Never overwrite a source snapshot or rewrite a published dataset version.

## Evidence and identity

- Published facts must resolve through Claim → Evidence → Source. Tier 3 sources may discover candidates but cannot independently support disputed claims or direct influence.
- Never convert visual or computational similarity into historical influence. Preserve `historical_relationship_strength`, `evidence_confidence`, `computational_similarity`, and `curatorial_relevance` separately.
- A publishable `artist` must be an identified, confirmed-deceased individual. Anonymous, workshop, collective, and traditional attributions are not silently converted into people.
- Preserve competing claims, counter-evidence, provenance, reviewer, review date, and status history.

## Rights and release

- Keep code, original text, metadata, media, audio, and video rights separate.
- Do not commit third-party media unless its record passes the rights gate and the file is explicitly in release scope.
- Never publish media with unknown rights or `development_only=true`.
- Do not put API keys, tokens, cookies, local credentials, or licensed source files in Git.

## Engineering and QA

- Prefer static, versioned release data. External APIs belong to acquisition jobs, not the public runtime.
- Update schemas, fixtures, tests, and policy together when a governance contract changes.
- Run the targeted validators and unit tests before committing. Treat an expected-invalid fixture that passes as a failure.
- A publishable release must be validated as a complete physical bundle. A manifest without resolvable files, hashes, typed IDs, reference closure, notices, attribution, or source/media permission is a hard failure.
- Never trust a record's requested schema: canonical dispatch is determined by entity type, branch, and ID prefix. Never replace a concrete branch schema with a common base schema.
- Source licenses use canonical registry snapshots and stable rule IDs. Every publishable consumer binds the exact rule/content class it used; Tier 4 and self-declared replacements for restricted canonical rules are blocked.
- Self-hosted media bytes, source-rule snapshots, license decisions, notices, and attributions must be real manifest files with exact ID/hash/content closure.
- Use project skills only when `skill/SKILL_INDEX.md` exists and names an applicable skill; never invent one.
- Keep changes surgical and document any unresolved decision rather than silently choosing it.
