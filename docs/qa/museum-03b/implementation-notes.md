# MUSEUM-03B implementation notes

## Entry and Wave 0

| Type | Expected | Discovered evidence | Decision / consequence | Validation |
|---|---|---|---|---|
| validation | Baseline, private bundle and Pages entry gates pass | Local/origin/GitHub `main` are `81ca9d28cfb16f971a582497448d30cd0579ee6c`; bundle validator has zero issues; baseline and live foyer smoke pass | Proceed with the already approved decision | Full pre-decision commands recorded for the phase report |
| discovery | Bundle hash alone closes the approved selection | The semantic bundle hash does not itself bind current candidate bytes or the physical Recommended file | Application receipt additionally binds the Recommended file SHA-256 and canonical hash of all 12 selected candidate records | Synthetic drift/idempotency/conflict tests pass |
| decision | Apply Recommended + Mixed once | Cross-document validation confirms authority Mays, exact 12 IDs, zero replacements and `Mixed → metadata-first` | Receipt `selection-decision-application:8c2666ef-fdfe-5250-af97-1d3b1d8c4a43`; OD-004/007 closed | Initial apply pass; repeat is idempotent and bytes unchanged |
| discovery | All MUSEUM-03A identity flags can be promoted directly | Existing source evidence contains a Raja Ravi Varma life-date/production-role conflict; other candidates also have precision and source-lineage gaps | Do not inherit preflight booleans. Wave 2 must preserve competing claims and resolve the hard gate before any artist promotion | No formal artist record written yet |

## Stop conditions

- Any approved artist with unresolved identity/death/external-ID conflict blocks formal 12-person promotion and later Waves 3–6.
- No artist may be replaced automatically.
- No media bytes, public release, Pages art content or MUSEUM-04 implementation are allowed in this phase.
