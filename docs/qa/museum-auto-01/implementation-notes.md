# MUSEUM-AUTO-01 implementation notes

## Entry 1

- Entry type: discovery
- Expected: approximately 36 modified and 98 untracked M04 files.
- Discovered: clean `main` at `15617a1d`, ahead of `origin/main` by one commit.
- Evidence: status, reflog, commit parent, and exact `A=98/M=36` parent diff.
- Conservative choice: preserve the commit, reconstruct the dirty inventory from Git evidence, and add a separate validated checkpoint without rewriting history.
- Consequence: the original dirty instant is not directly observable, but its exact path set is recoverable.
- Validation: local `main` is a fast-forward descendant of remote `main`.

## Entry 2

- Entry type: validation
- Expected: M03B is the immutable input baseline.
- Discovered: package validator, package hash, graph hash, counts, media distribution, and zero-byte state all match the declared baseline; checkpoint diff is empty for M03B sealed paths.
- Evidence: package validator plus package/graph manifest checks.
- Conservative choice: consume M03B but never rewrite it.
- Consequence: M03C outputs must live under new versioned paths.
- Validation: `12/44/31/36`, `0/0/36`, `31/4/9`, zero media bytes.

## Entry 3

- Entry type: decision
- Expected: generated outputs can be rebuilt.
- Discovered: old dist/test/tmp outputs and tracked M04 candidate release are reproducible; protected raw/review data is separate.
- Evidence: path classification and recovery manifests.
- Conservative choice: hash-copy all WIP and protected data outside the repository; remove only verified ignored build/test/cache directories.
- Consequence: no source or reviewed data is lost; stale outputs cannot contaminate later validation.
- Validation: every recovery entry has equal source/destination SHA-256.
