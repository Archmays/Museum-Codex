# MUSEUM-04 dependency verification

Verified: 2026-07-14

## Production choice

- `graphology@0.26.0` is the latest stable Graphology release shown by the official release feed.
- `sigma@3.0.3` is the latest stable Sigma release shown by the official release feed. Sigma 4 is still published as an alpha line and is excluded.
- Both direct graph dependencies and every resolved production transitive dependency declare MIT in `package-lock.json`.
- Direct versions are exact semver values. The lockfile records the npm registry tarball and SHA-512 integrity for every resolved package.
- The route imports Graphology and Sigma only through the lazy `#/art/constellation` feature. The build uses no CDN or remote worker.

Official basis: [Graphology releases](https://github.com/graphology/graphology/releases), [Sigma 3.0.3 release](https://github.com/jacomyal/sigma.js/releases/tag/sigma%403.0.3), [Sigma releases](https://github.com/jacomyal/sigma.js/releases).

## Notices and automated guard

The deployable [third-party software notice](../../../public/THIRD_PARTY_NOTICES.md) records every production package, resolved version, copyright notice, and the common MIT terms. `tests/test_museum_04_dependencies.py` fails if the production dependency set, exact graph versions, lock provenance, license, notice coverage, private package flag, or no-project-`LICENSE` decision drifts.

Verification commands:

```powershell
npm ls --omit=dev --all
python -m unittest tests.test_museum_04_dependencies
```
