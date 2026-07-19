# MUSEUM-08 withdrawal, rollback, and recovery checklist

## Rehearsal boundary

The rehearsal is completely synthetic. It does not change any artist, artwork, media, relationship, place episode, release manifest, or deployed byte from the public dataset.

Four isolated cases are executed:

1. media asset withdrawal → new release removes the media reference and exposes the no-image equivalent;
2. relationship withdrawal → relationship and every path that depends on it are removed;
3. place episode withdrawal → map, timeline, and list omit the episode;
4. artwork metadata withdrawal → gallery/search references are removed and the stable URL explains that the record is unavailable.

Every case updates notices, preserves predecessor bytes, and requires reference closure before a release can be selected.

## Pages rollback procedure

1. Freeze deploy ownership to one operator and stop concurrent candidate deploys.
2. Preserve the failed candidate artifact, workflow logs, deployment ID, and exact commit.
3. Select the last successful predecessor artifact by exact commit and release ID.
4. Verify predecessor manifest SHA, content hash, physical tree hash, file count, and byte count against the release-integrity ledger.
5. Confirm no secrets, private data, task scratch, or local absolute paths are present.
6. Deploy the predecessor artifact without rebuilding an immutable historical release.
7. Verify loader selection plus home, gallery, artwork/no-image, compare, tours, paths, map list, rights, and media byte closure.
8. Verify withdrawn/missing URLs retain natural-language recovery and do not create broken references.
9. Record operator, trigger, deployment ID, commit, release ID, all hashes, start/end time, and online probe results.
10. Reopen candidate work only through a new immutable candidate and the affected CI closure.

## Recovery objectives

- RTO: 15 minutes from rollback authorization to predecessor verification/deploy under normal Pages availability.
- RPO: zero mutation of any published release; a failed candidate may be abandoned, but predecessor bytes and history remain unchanged.
- Pages platform outage is recorded separately and never converted into a false successful rehearsal.

## Evidence

- Candidate records: `withdrawal-rehearsal.json`, `rollback-rehearsal.json`
- Executable simulation: `museum_pipeline/art/candidate.py`
- Targeted tests: `tests/test_museum_08_recovery.py`
- Online closure is recorded in `online-closure.json` and the MUSEUM-08 phase report after the single candidate deployment.
