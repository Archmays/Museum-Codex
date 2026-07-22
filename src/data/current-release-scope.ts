import { CURRENT_ART_RELEASE_ID, currentArtReleaseBaseUrl } from "./art-release-profile";
import { loadStaticRelease } from "./release-loader";

export type CurrentReleaseScope = {
  artists: number;
  artworks: number;
  galleryProfiles: number;
  collectionProfiles: number;
  selfHostedWorks: number;
  externalLinkOnlyWorks: number;
  metadataOnlyWorks: number;
};

let scopePromise: Promise<CurrentReleaseScope> | null = null;

function integer(value: unknown, field: string) {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
    throw new Error(`invalid_current_scope_${field}`);
  }
  return value;
}

async function digestHex(bytes: ArrayBuffer) {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function fetchScope() {
  const base = new URL(currentArtReleaseBaseUrl(), window.location.href);
  const manifestResult = await loadStaticRelease(new URL("manifest.json", base).href);
  if (manifestResult.status !== "loaded" || manifestResult.manifest.id !== CURRENT_ART_RELEASE_ID) {
    throw new Error("current_scope_manifest_unavailable");
  }
  const reference = manifestResult.manifest.manifest_files.find((file) => file.path === "validation-summary.json");
  if (!reference) throw new Error("current_scope_reference_missing");
  const response = await fetch(new URL(reference.path, base), { headers: { Accept: "application/json" } });
  const bytes = await response.arrayBuffer();
  if (!response.ok || bytes.byteLength !== reference.bytes || await digestHex(bytes) !== reference.sha256.replace(/^sha256:/, "")) {
    throw new Error("current_scope_integrity_failure");
  }
  const document = JSON.parse(new TextDecoder().decode(bytes)) as { status?: unknown; counts?: Record<string, unknown> };
  if (document.status !== "pass" || !document.counts) throw new Error("current_scope_not_publishable");
  const scope = {
    artists: integer(document.counts.artists, "artists"),
    artworks: integer(document.counts.artworks, "artworks"),
    galleryProfiles: integer(document.counts.gallery_profiles, "gallery_profiles"),
    collectionProfiles: integer(document.counts.collection_profiles, "collection_profiles"),
    selfHostedWorks: integer(document.counts.self_hosted_works, "self_hosted_works"),
    externalLinkOnlyWorks: integer(document.counts.external_link_only_works, "external_link_only_works"),
    metadataOnlyWorks: integer(document.counts.metadata_only_works, "metadata_only_works"),
  };
  if (
    scope.galleryProfiles + scope.collectionProfiles !== scope.artists ||
    scope.selfHostedWorks + scope.externalLinkOnlyWorks + scope.metadataOnlyWorks !== scope.artworks
  ) throw new Error("current_scope_count_closure");
  return scope;
}

export function loadCurrentReleaseScope() {
  scopePromise ??= fetchScope();
  return scopePromise;
}
