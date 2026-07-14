# MUSEUM-04 renderer benchmark

This is a deterministic, synthetic, repository-only harness for the `1k V / 5k E` scale profile. It builds the full Graphology model, projects the mobile cap (`150 V / 600 E`), and exercises the production Sigma 3.0.3 dotted-edge renderer. It contains no museum records and is never included in `dist` or the public release.

The controlled-lab runner starts this harness through its dedicated Vite config. Raw browser artifacts belong under ignored `output/playwright/`; only the validated aggregate evidence JSON is committed under `docs/qa/museum-04/`.
