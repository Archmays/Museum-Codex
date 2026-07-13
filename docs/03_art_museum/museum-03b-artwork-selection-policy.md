# MUSEUM-03B artwork selection policy

## Scope

This policy governs the internal reviewed artwork layer for `art-batch:museum-03b-first-slate-v1`. It applies only to the exact twelve artists approved by the committed MUSEUM-03B selection decision. It does not authorize a replacement artist, a public art release, MUSEUM-04, or media acquisition.

## Fixed selection budget

The formal target is 44 official object records. Ten artists contribute four records; Käthe Kollwitz and Raja Ravi Varma contribute two each. A valid batch has at least two records for every approved artist and never increases another artist's quota to hide a source gap.

Mary Cassatt's four selected records are the Art Institute of Chicago objects `111442`, `13506`, `26650`, and `28826`. Four reviewed holdouts remain excluded, but their identifiers are intentionally omitted from tracked data because unapproved alternatives are outside the public-Git boundary. The complete approved object list and the aggregate holdout count/hash live in `research/art/museum-03b-artwork-selection-basis.json`.

## Object closure

Every formal artwork must bind an exact Met or AIC object record and preserve:

- stable artwork, source-object, institution, and accession identifiers;
- source title plus a reviewed `zh-Hans` project translation with provenance;
- the institution's creator display and controlled attribution type;
- the institution's date display at its actual precision;
- material, technique, and optional subject context IDs;
- Claim → Evidence → Source links with raw snapshot receipt and source-rule closure;
- a separate media-eligibility assessment;
- attribution, multilingual, rights, and data-review sign-offs;
- uncertainty and append-only status history.

Official collection metadata is evidence of the institution's cataloguing statement. It is not silently generalized into personal physical execution, historical influence, or media permission.

## Attribution and date safeguards

- Met `artistPrefix` and AIC credit text control the formal attribution projection; the MUSEUM-03A flattened preflight value is not authoritative.
- All selected Shen Zhou records retain `attributed_to`.
- Cassatt AIC `13506` retains the collaboration/printing credit rather than erasing it.
- Raja Ravi Varma objects dated circa 1910 retain the Met association but remain disputed as personal execution because the accepted death year is 1906.
- Missing object display dates are recorded as unknown or broadly bounded. Artist life dates must never be substituted for object dates.
- A changed or competing attribution/date remains counter-evidence; it is not overwritten.

## Selection rationale

Selection considers chronology, medium, material, subject, comparison questions, relationship evidence, object-record stability, and rights readiness. Fame, market value, image availability, and ease of downloading are not selection criteria.

## Failure conditions

The artwork gate fails if an object record is absent, an attribution display is flattened, date precision is inflated, institution/accession closure is missing, any approved artist has fewer than two records, an unapproved artist is introduced, metadata rights are inherited by media, a long museum description is copied, a media URL is treated as permission, or any record is promoted to `published`.

## Public leakage matching

The tracked public-artifact deny-list uses strict substring matching for approved artist labels, artist aliases, and artwork titles, and exact-token matching for formal IDs and external IDs. Context labels remain in the deny-list but use standalone serialized-string matching because common vocabulary such as `Canvas` or `Ink` can already occur legitimately in CSS, accessibility keywords, or an empty-antechamber description. A context label serialized as a data value still fails closed; an ordinary prose or CSS occurrence does not by itself establish reviewed-record leakage.

## Phase boundary

The output is reviewed metadata. No image, tile, IIIF payload, derivative, or generated substitute enters Git or Pages in MUSEUM-03B.
