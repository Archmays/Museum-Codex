# MUSEUM-03C implementation notes

- Entry gate preserved the sealed M03B package and exact package/graph hashes.
- Network is offline by default. Live discovery and live media acquisition are separate explicit actions; acquisition requires both `--live` and `--download-media`.
- Original bytes and network evidence are ignored under `data/media-source/art/museum-03c/`; only validated derivatives and governed records enter the tracked bundle.
- Direct HTTPS deliberately bypasses the machine proxy. DNS addresses must all be public, the actual TLS peer must belong to the validated set, and every redirect repeats the same gate.
- AIC and Commons are single-threaded with at least one second between requests. No cookies, authorization headers or arbitrary URLs are accepted.
- Four AIC public-domain image IDs remained rights-eligible but their official IIIF host returned HTTP 403. They were not converted into external approvals without byte closure.
- Nine metadata-only works received an explicit Commons supplementary search. Search results remain discovery-only because object corroboration, permanent revision/license/dispute state and visual identity did not all close.
- JPEG/WebP derivatives use EXIF orientation, ICC normalization when present, metadata stripping, LANCZOS resize and compression only. Transparent sources fail closed rather than being silently flattened.
- Each derivative maps to one media ID and one physical path; artwork-level responsive sets are assembled later without weakening the physical validator.
- M03B validator code-anchor logic now treats the historical commit as a required ancestor while current schemas still validate every sealed record. This prevents append-only later schema registrations from falsely invalidating unchanged M03B bytes.
