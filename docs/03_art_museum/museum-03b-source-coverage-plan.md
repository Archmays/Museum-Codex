# MUSEUM-03B source coverage plan

Status: reviewed source plan, not a public release  
Verified: 2026-07-13  
Batch: `art-batch:museum-03b-first-slate-v1`

This plan covers exactly the twelve artists in the submitted Recommended Slate. It does not approve a substitute, download media, or authorize public-runtime access. Formal facts must still close through `Claim -> Evidence -> Source` and receive the role-specific reviews described below.

## Registered source basis

| Source | Role | Current execution state | Exact rule bindings | 2026-07-13 check |
|---|---|---|---|---|
| `getty_ulan` | Tier 1 identity, names, life observations, authority links | `reference_adapter_ready` | `getty_ulan:data:eb25ddb4d400`; media rule prohibits use | All 12 exact ULAN records returned HTTP 200 through adapter `0.1.1`; no contract drift |
| `met_open_access` | Tier 1 official collection objects and object-level media status | `reference_adapter_ready` | `met_open_access:data:8924a3c83dc7`; `met_open_access:media:1669574588c7` | Exact object `436244` returned HTTP 200 through adapter `0.1.0`; metadata and media remain separate |
| `aic_api` | Tier 1 official collection objects and object-level media status | `reference_adapter_ready` | `aic_api:data:75df7e022b4e`; descriptions use separate CC BY rule; `aic_api:media:98cceb1965b8` | Exact object `60513` returned HTTP 200 through adapter `0.1.0`; no description field was requested |
| `wikidata` | Tier 3 discovery and external-ID conflict checking only | `discovery_only` | `wikidata:data:dab022172e7e`; media rule prohibits use | Exact Tanner QIDs were captured to investigate a cross-link conflict; Tier 3 is not used to establish death, authorship, or influence |

Endpoint registry SHA-256: `sha256:77f33683b9eabe64e5e3f18900bdf949240fe71387ae08ad12d98cd83d31a114`  
License rules SHA-256: `sha256:19d10386405abf971c5712e955f60c08d2bd43e6f8060a29035033ff3c33ada2`

Getty's official obtain/LOD pages were rechecked: current individual-record JSON/Linked Data and ODC-By 1.0 remain available; the discontinued XML services remain prohibited. The Met API still exposes selected collection data under CC0 and requires object-level Open Access evidence for images. AIC remains field-sensitive: artwork `description` is not silently treated as CC0, and IIIF availability is not media permission.

## Artist-by-artist coverage

`Collection objects` is a coverage role, not an identity-independent duplicate of Getty. Every formal artwork must bind its own exact object record and media assessment.

| Approved artist | Stable authority | Birth/death plan | Collection objects | Relationship evidence plan | Current gate note |
|---|---|---|---|---|---|
| Albrecht Dürer | ULAN `500115493` | Getty Tier 1 plus official collection corroboration | Met, 4 exact objects | Exact museum/scholarly locators; no similarity inference | ready for identity review |
| Francisco de Goya | ULAN `500118936` | Getty Tier 1 plus official collection corroboration | Met, 4 exact objects | Exact museum/scholarly locators | ready for identity review |
| Vincent van Gogh | ULAN `500115588` | Getty Tier 1 plus official collection corroboration | Met, 4 exact objects | Exact museum/scholarly locators | ready for identity review |
| Mary Cassatt | ULAN `500012368` | Getty Tier 1 plus official collection corroboration | AIC/Met; select 4 exact objects | Exact museum/scholarly locators | ready for identity review |
| Käthe Kollwitz | ULAN `500016751` | Getty Tier 1 plus official collection corroboration | AIC, 2 exact objects | Exact museum/scholarly locators | small quota is explicit, not filled by another artist |
| Julia Margaret Cameron | ULAN `500118804` | Getty Tier 1 plus official collection corroboration | Met, 4 exact objects | Exact museum/scholarly locators | ready for identity review |
| Katsushika Hokusai | ULAN `500060426` | Getty Tier 1 plus official collection corroboration | Met, 4 exact objects | Exact museum/scholarly locators | names must preserve source forms/transliterations |
| Kitagawa Utamaro | ULAN `500054492` | competing circa 1753/1754 observations must remain approximate | Met, 4 exact objects | Exact museum/scholarly locators | birth projection cannot be exact |
| Shen Zhou | ULAN `500121310` | Getty Tier 1 plus official collection corroboration | Met, 4 exact objects | Exact museum/scholarly locators | original Chinese names and historical geography required |
| Raja Ravi Varma | ULAN `500122641` | competing 1906/1907 observations require explicit adjudication | Met, 2 exact records; creator/press role must be reviewed | Exact institutional/scholarly locators | identity promotion stops until date and object-role conflicts close |
| José Guadalupe Posada | ULAN `500032573` | Getty Tier 1 plus official collection corroboration | Met, 4 exact objects | Exact museum/scholarly locators | ready for identity review |
| Henry Ossawa Tanner | ULAN `500005351` | Getty Tier 1 plus official collection corroboration | Met, 4 exact objects | Exact museum/scholarly locators | Getty's erroneous-looking `same_as` link must be adjudicated against reciprocal IDs |

For every person the minimum formal closure is: one authority source; sourced birth and death Claims; at least one official artwork/history record; source-lineage analysis; exact source/license bindings; and separate identity and art-history review records. A single automated step cannot collect and approve the record.

## Manual capture contract

Manual capture is permitted only for a named official institutional page required to resolve a gap. It records the official HTTPS URL, access time, page title and publisher, exact field/section locator, normalized factual field, raw-capture SHA-256, terms URL, source tier, and reviewer. Raw page/screenshot bytes stay in the ignored immutable evidence area. Tracked data may contain only permitted normalized facts, hashes, and short locators. No generic arbitrary-URL scraper will be added.

If a new institution is required, its canonical host, source tier, metadata/media split, stable rule IDs, terms verification and reverify dates, access limits, redistribution decision, and exact endpoint/profile must be registered before a formal record binds it.

## Independence and threat review

- Getty supplies authority observations compiled from contributors; a Met or AIC object record is an independent collection role, not automatically an independent biographical source.
- Wikidata is discovery-only and is never counted as the Tier 1/2 death, attribution, or relationship source.
- Reciprocal external IDs are checked by entity meaning, dates, and authority identifiers; name equality is insufficient.
- DNS, redirects, and system proxy configuration remain part of the host trust boundary. Adapters keep allowlisted scheme/host/path/query profiles, reject unregistered redirects, and record immutable hashes.
- The ignored raw store is append-only by application convention, not filesystem WORM. Snapshot collision checks, immutable paths, hashes, and manifest validation are the current mitigation.
- Discovery utilities do not become reference adapters. Only registered fixed-source adapters or the strict manual capture contract can supply formal evidence.

## P3 review register

| ID | Owner | Reason | Current mitigation | Impact | Recheck no later than | Blocks MUSEUM-04 |
|---|---|---|---|---|---|---|
| P3-01 | data/release reviewer | Application append-only storage is not WORM | collision refusal, immutable paths, SHA-256 closure, Git history | tamper resistance depends on host controls | MUSEUM-05 media/release hardening | no |
| P3-02 | security/data reviewer | DNS and the system proxy are outside adapter pinning | canonical HTTPS hosts, redirect allowlists, exact paths/query names, response hashes | a compromised local/network trust layer could affect live capture | before any scheduled production acquisition | no |
| P3-03 | source/adapter owner | Discovery helpers lack a reference-adapter contract | discovery-only status; no formal promotion; fixed manual contract | fewer sources can be automated in this batch | before adding any new production adapter | no |

The two identity conflicts above are not P3 items: they are Wave 2 hard-gate work and must be explicitly resolved or the phase becomes blocked.
