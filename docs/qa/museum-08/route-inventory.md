# MUSEUM-08 route inventory

Candidate release 中的 canonical JSON 为 `route-inventory.json`。本表是 reader-facing mirror；具体数量只属于 V1 candidate invariant，不是共享运行时上限。

| Route | Concrete routes | Lazy chunk | Data strategy | Low-bandwidth / WebGL | Print | Missing / withdrawal |
|---|---:|---|---|---|---|---|
| `/` | 1 | shell | no artwork data | no WebGL/media | supported | shell remains |
| `/art` | 1 | shell | destinations only | no WebGL/media | supported | shell remains |
| `/art/constellation` | 1 | art-constellation | metadata, relationships on demand | list default; Sigma forbidden | metadata | natural unavailable state |
| `/art/artists` | 1 | art-gallery | artist index | no index image | supported | natural unavailable state |
| `/art/artists/:artistId` | 12 | art-gallery | stable-ID detail | image only after action | supported | missing/withdrawn explanation |
| `/art/artworks/:artworkId` | 44 | art-gallery | stable-ID detail | image only after action | supported | no-image or missing explanation |
| `/art/compare` | 1 | art-gallery | metadata first | stacked, no automatic image | supported | remaining work stays usable |
| `/art/tours` | 1 | art-gallery | tour index | metadata only | supported | natural unavailable state |
| `/art/tours/:tourId` | 18 | art-gallery | stable-ID tour | image only after action | supported | missing explanation |
| `/art/paths` | 1 | art-paths | path graph/index | complete text view; WebGL forbidden | text | missing edge is removed |
| `/art/map` | 1 | art-map | map index/episodes | timeline/list; MapLibre forbidden | list/timeline | missing episode is removed |
| `/art/search` | 1 | art-search | manifest then hash-verified shards | media forbidden | results | failed index retains site routes |
| `/about` | 1 | shell | static copy | no media/WebGL | supported | shell remains |
| `/rights` | 1 | shell | static copy + notice links | no media/WebGL | supported | shell remains |
| `/accessibility` | 1 | shell | static copy/preferences | no media/WebGL | supported | shell remains |
| `/*` | 1 | shell | none | no media/WebGL | not applicable | natural-language recovery |

Every template records keyboard/skip/focus, no-script copy, rights/source entry, reserved loading viewport, and withdrawal fallback in the candidate JSON. Concrete count: 87; template count: 16.
