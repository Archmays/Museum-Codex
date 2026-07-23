import type {
  ArtConstellationDataSource,
  ArtConstellationRelease,
  ArtistRecord,
  ArtistSources,
  ArtworkCatalog,
  ArtworkDetails,
  ArtworkMediaDecision,
  ArtworkRecord,
  ClaimRecord,
  ContextRecord,
  DetailLoadResult,
  EvidenceRecord,
  GraphSummary,
  LayoutNode,
  LocalizedText,
  MediaAsset,
  RelationshipDetails,
  RelationshipExplorerConfig,
  RelationshipIndex,
  RelationshipRecord,
  RelationshipType,
  RightsDetails,
  RightsRecord,
  SearchEntry,
  SourceRecord,
  ThirdPartyNotice,
} from "../features/art-constellation/types";
import { readBootstrappedArtifact, type BootstrappedArtifact } from "./art-constellation-bootstrap";

export const SUPPORTED_RELEASE_SCHEMA_MAJOR = 1;

type ArtifactReference = { path: string; sha256: string };
type ManifestFile = ArtifactReference & {
  bytes: number;
  record_type: string;
  schema_path: string | null;
  record_ids: string[];
};

export type RuntimeAssetFile = ArtifactReference & {
  bytes: number;
  record_type: string;
  record_ids: string[];
  source_path?: string;
  resolved_path?: string;
  delivery_mode?: string;
};

export type AssetResolutionManifest = {
  id: string;
  schema_version: string;
  release_id: string;
  content_hash: string;
  referenced_files: RuntimeAssetFile[];
  materialized_asset_files: RuntimeAssetFile[];
  referenced_file_count: number;
  materialized_asset_count: number;
  new_public_original_count: 0;
  runtime_external_image_request_count: 0;
};

type ReleaseLifecycle =
  | { status: "reviewed"; public_release: false }
  | { status: "publishable" | "published"; public_release: true };

export type ReleaseManifest = {
  schema_version: string;
  id: string;
  entity_type: "dataset_release";
  version: string;
  schema_versions: Record<string, string>;
  build_version: string;
  created_at: string;
  source_snapshot_at: string;
  content_hash: string;
  predecessor: string | null;
  public_until: string | null;
  included_entity_ids: string[];
  included_relationship_ids: string[];
  included_claim_ids: string[];
  included_evidence_ids: string[];
  included_source_ids: string[];
  included_media_asset_ids: string[];
  withdrawals: unknown[];
  deprecations: unknown[];
  manifest_files: ManifestFile[];
  referenced_files?: RuntimeAssetFile[];
  materialized_asset_files?: RuntimeAssetFile[];
  license_decisions: {
    code_license_decision_id: string;
    code_license_status: "decided" | "not_applicable";
    original_content_license_decision_id: string;
    original_content_license_status: "decided" | "not_applicable";
    third_party_scope_statement: string;
    registry_path: string;
    registry_sha256: string;
  };
  source_registry_manifest: ArtifactReference;
  third_party_notices_manifest: ArtifactReference;
  attribution_manifest: ArtifactReference & { asset_ids: string[] };
  release_notes: string;
} & ReleaseLifecycle;

export type ReleaseLoadResult =
  | { status: "missing" }
  | { status: "empty"; manifest: ReleaseManifest }
  | { status: "incompatible"; foundVersion: string }
  | { status: "loaded"; manifest: ReleaseManifest }
  | { status: "failed" };

type ReleaseLogger = (event: "missing" | "incompatible" | "failed", detail?: string) => void;

const SHA256 = /^(?:sha256:)?[a-f0-9]{64}$/;
const SEMVER = /^\d+\.\d+\.\d+$/;
const SAFE_PATH = /^(?!\/)(?!.*\\)(?!.*:)(?!.*(?:^|\/)\.\.(?:\/|$))[A-Za-z0-9._/-]+$/;

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isArtifactReference(value: unknown): value is ArtifactReference {
  return (
    isRecord(value) &&
    typeof value.path === "string" &&
    SAFE_PATH.test(value.path) &&
    typeof value.sha256 === "string" &&
    SHA256.test(value.sha256)
  );
}

function isManifestFile(value: unknown): value is ManifestFile {
  if (!isRecord(value)) return false;
  const bytes = value.bytes;
  const recordType = value.record_type;
  const schemaPath = value.schema_path;
  const recordIds = value.record_ids;
  return (
    isArtifactReference(value) &&
    typeof bytes === "number" &&
    Number.isInteger(bytes) &&
    bytes >= 0 &&
    typeof recordType === "string" &&
    (schemaPath === null || (typeof schemaPath === "string" && SAFE_PATH.test(schemaPath))) &&
    isStringArray(recordIds)
  );
}

function isRuntimeAssetFile(value: unknown): value is RuntimeAssetFile {
  if (!isRecord(value)) return false;
  const record = value;
  if (!isArtifactReference(record)) return false;
  const candidate = record as ArtifactReference & Record<string, unknown>;
  return (
    Number.isInteger(candidate.bytes) && Number(candidate.bytes) >= 0 &&
    typeof candidate.record_type === "string" &&
    isStringArray(candidate.record_ids) &&
    (candidate.source_path === undefined || (typeof candidate.source_path === "string" && SAFE_PATH.test(candidate.source_path))) &&
    (candidate.resolved_path === undefined || (typeof candidate.resolved_path === "string" && SAFE_PATH.test(candidate.resolved_path))) &&
    (candidate.delivery_mode === undefined || typeof candidate.delivery_mode === "string")
  );
}

function hasArtifactClosure(files: ManifestFile[], reference: ArtifactReference, recordType: string) {
  return files.some(
    (file) => file.path === reference.path && file.sha256 === reference.sha256 && file.record_type === recordType,
  );
}

function sameSet(left: string[], right: string[]) {
  const uniqueLeft = [...new Set(left)];
  const uniqueRight = [...new Set(right)];
  return uniqueLeft.length === uniqueRight.length && uniqueLeft.every((item) => uniqueRight.includes(item));
}

function recordIdsFor(files: ManifestFile[], recordType: string) {
  return files.filter((file) => file.record_type === recordType).flatMap((file) => file.record_ids);
}

function isLicenseDecisions(value: unknown): value is ReleaseManifest["license_decisions"] {
  if (!isRecord(value)) return false;
  return (
    typeof value.code_license_decision_id === "string" &&
    (value.code_license_status === "decided" || value.code_license_status === "not_applicable") &&
    typeof value.original_content_license_decision_id === "string" &&
    (value.original_content_license_status === "decided" || value.original_content_license_status === "not_applicable") &&
    typeof value.third_party_scope_statement === "string" && value.third_party_scope_statement.length > 0 &&
    typeof value.registry_path === "string" && SAFE_PATH.test(value.registry_path) &&
    typeof value.registry_sha256 === "string" && SHA256.test(value.registry_sha256)
  );
}

function isCanonicalRelease(value: unknown): value is ReleaseManifest {
  if (!isRecord(value)) return false;
  const includedEntityIds = value.included_entity_ids;
  const includedRelationshipIds = value.included_relationship_ids;
  const includedClaimIds = value.included_claim_ids;
  const includedEvidenceIds = value.included_evidence_ids;
  const includedSourceIds = value.included_source_ids;
  const includedMediaAssetIds = value.included_media_asset_ids;
  if (
    !isStringArray(includedEntityIds) ||
    !isStringArray(includedRelationshipIds) ||
    !isStringArray(includedClaimIds) ||
    !isStringArray(includedEvidenceIds) ||
    !isStringArray(includedSourceIds) ||
    !isStringArray(includedMediaAssetIds)
  ) return false;
  if (!Array.isArray(value.withdrawals) || !Array.isArray(value.deprecations)) return false;
  if (!Array.isArray(value.manifest_files) || value.manifest_files.length === 0 || !value.manifest_files.every(isManifestFile)) return false;
  if (value.referenced_files !== undefined && (!Array.isArray(value.referenced_files) || !value.referenced_files.every(isRuntimeAssetFile))) return false;
  if (value.materialized_asset_files !== undefined && (!Array.isArray(value.materialized_asset_files) || !value.materialized_asset_files.every(isRuntimeAssetFile))) return false;
  if (!isRecord(value.schema_versions) || Object.keys(value.schema_versions).length === 0) return false;
  if (!Object.values(value.schema_versions).every((version) => typeof version === "string" && SEMVER.test(version))) return false;
  const licenseDecisions = value.license_decisions;
  if (!isLicenseDecisions(licenseDecisions)) return false;
  if (!isArtifactReference(value.source_registry_manifest) || !isArtifactReference(value.third_party_notices_manifest)) return false;
  const attribution = value.attribution_manifest;
  const includedMediaIds = includedMediaAssetIds;
  if (!isRecord(attribution)) return false;
  const attributionAssetIds = attribution.asset_ids;
  if (!isArtifactReference(attribution) || !isStringArray(attributionAssetIds)) return false;
  if (!isStringArray(includedMediaIds)) return false;

  const files = value.manifest_files;
  const runtimeAssetFiles = [
    ...(value.referenced_files ?? []),
    ...(value.materialized_asset_files ?? []),
  ];
  const mediaClosureFiles: RuntimeAssetFile[] = [...files, ...runtimeAssetFiles].filter((file) => file.record_type === "media");
  const identityIsValid =
    typeof value.schema_version === "string" &&
    SEMVER.test(value.schema_version) &&
    typeof value.id === "string" &&
    /^release:[a-z0-9][a-z0-9._-]*$/.test(value.id) &&
    value.entity_type === "dataset_release" &&
    typeof value.version === "string" && SEMVER.test(value.version);
  const lifecycleIsAllowed =
    (
      (value.status === "publishable" || value.status === "published") && value.public_release === true
    ) &&
    (value.predecessor === null || typeof value.predecessor === "string") &&
    (value.public_until === null || typeof value.public_until === "string");
  const buildMetadataIsValid =
    typeof value.build_version === "string" && value.build_version.length > 0 &&
    typeof value.created_at === "string" && value.created_at.length > 0 &&
    typeof value.source_snapshot_at === "string" && value.source_snapshot_at.length > 0 &&
    typeof value.content_hash === "string" && /^sha256:[a-f0-9]{64}$/.test(value.content_hash) &&
    typeof value.release_notes === "string" && value.release_notes.length > 0;
  const includedRecordIds = [
    ...includedEntityIds,
    ...includedRelationshipIds,
    ...includedClaimIds,
    ...includedEvidenceIds,
    ...includedSourceIds,
    ...includedMediaIds,
  ];
  const licenseDecisionIds = [
    licenseDecisions.code_license_decision_id,
    licenseDecisions.original_content_license_decision_id,
  ];
  const closureIsPresent =
    hasArtifactClosure(files, value.source_registry_manifest, "source_registry") &&
    hasArtifactClosure(files, value.third_party_notices_manifest, "third_party_notices") &&
    hasArtifactClosure(files, attribution, "attributions") &&
    files.some(
      (file) =>
        file.path === licenseDecisions.registry_path &&
        file.sha256 === licenseDecisions.registry_sha256 &&
        file.record_type === "license_decisions",
    ) &&
    sameSet(attributionAssetIds, includedMediaIds) &&
    sameSet(recordIdsFor(files, "data"), includedRecordIds) &&
    sameSet(recordIdsFor(files, "source_registry"), includedSourceIds) &&
    mediaClosureFiles.every((file) => file.record_ids.length > 0) &&
    mediaClosureFiles.flatMap((file) => file.record_ids).every((id) => includedMediaIds.includes(id)) &&
    new Set(mediaClosureFiles.flatMap((file) => file.record_ids)).size === mediaClosureFiles.flatMap((file) => file.record_ids).length &&
    sameSet(recordIdsFor(files, "third_party_notices"), [...includedSourceIds, ...includedMediaIds]) &&
    sameSet(recordIdsFor(files, "attributions"), includedMediaIds) &&
    sameSet(recordIdsFor(files, "license_decisions"), licenseDecisionIds);

  return identityIsValid && lifecycleIsAllowed && buildMetadataIsValid && closureIsPresent;
}

function defaultLogger(event: "missing" | "incompatible" | "failed", detail?: string) {
  if (import.meta.env.DEV) console.info(`[museum-release] ${event}`, detail ?? "");
}

async function fetchJsonBytes(
  url: string,
  fetcher: typeof fetch,
  signal?: AbortSignal,
): Promise<BootstrappedArtifact> {
  const bootstrapped = fetcher === globalThis.fetch
    ? await readBootstrappedArtifact(url, signal)
    : null;
  if (bootstrapped) return bootstrapped;
  const response = await fetcher(url, { headers: { Accept: "application/json" }, signal });
  return {
    status: response.status,
    ok: response.ok,
    bytes: await response.arrayBuffer(),
  };
}

/**
 * Loads only the browser descriptor of a release that has already passed the
 * repository's Python physical-bundle validator. Runtime shape checks are a
 * fail-closed defense; they do not replace byte/hash validation at build time.
 */
export async function loadStaticRelease(
  manifestUrl: string,
  fetcher: typeof fetch = fetch,
  logger: ReleaseLogger = defaultLogger,
  signal?: AbortSignal,
): Promise<ReleaseLoadResult> {
  try {
    const response = await fetchJsonBytes(manifestUrl, fetcher, signal);
    if (response.status === 404) {
      logger("missing");
      return { status: "missing" };
    }
    if (!response.ok) {
      logger("failed", `http_${response.status}`);
      return { status: "failed" };
    }

    const data: unknown = JSON.parse(new TextDecoder().decode(response.bytes));
    if (!isRecord(data) || typeof data.schema_version !== "string") {
      logger("failed", "invalid_manifest_shape");
      return { status: "failed" };
    }
    const major = Number.parseInt(data.schema_version.split(".")[0] ?? "", 10);
    if (major !== SUPPORTED_RELEASE_SCHEMA_MAJOR) {
      logger("incompatible", data.schema_version);
      return { status: "incompatible", foundVersion: data.schema_version };
    }
    if (!isCanonicalRelease(data)) {
      logger("failed", "release_not_publishable_or_incomplete");
      return { status: "failed" };
    }

    const displayItemCount =
      data.included_entity_ids.length +
      data.included_relationship_ids.length +
      data.included_claim_ids.length +
      data.included_media_asset_ids.length;
    return displayItemCount === 0 ? { status: "empty", manifest: data } : { status: "loaded", manifest: data };
  } catch {
    logger("failed", "request_or_parse_error");
    return { status: "failed" };
  }
}

export function releaseMessage(status: ReleaseLoadResult["status"], locale: "zh-CN" | "en") {
  const messages = {
    "zh-CN": {
      missing: "正式馆藏正在整理，欢迎先参观门户与序厅。",
      empty: "展陈资料尚在整理，目前可以参观门户与序厅。",
      incompatible: "这批展陈资料需要更新后才能展示。",
      failed: "展陈资料暂时无法载入，请稍后再试。",
      loaded: "展陈资料已载入。",
    },
    en: {
      missing: "The collection is being prepared. You can still visit the portal and foyer.",
      empty: "Exhibition material is being prepared. The portal and foyer remain available.",
      incompatible: "This exhibition release needs an update before it can be displayed.",
      failed: "Exhibition material could not be loaded. Please try again later.",
      loaded: "Exhibition material is available.",
    },
  } as const;
  return messages[locale][status];
}

const ART_CONSTELLATION_SCHEMA_VERSION = "1.0.0";
const ART_CONSTELLATION_INITIAL_ARTIFACTS = [
  "graph-summary.json",
  "artists.json",
  "search-index.json",
  "layout.json",
  "facets.json",
] as const;
const ASSET_RESOLUTION_ARTIFACT = "asset-resolution-manifest.json";
const ART_CONSTELLATION_DECLARED_ARTIFACTS = [
  ...ART_CONSTELLATION_INITIAL_ARTIFACTS,
  "contexts.json",
  "relationships.json",
  "artworks.json",
  "claims.json",
  "evidence.json",
  "sources.json",
  "rights.json",
  "media-index.json",
  "withdrawal-mapping.json",
] as const;
const RELATIONSHIP_TYPES = ["shared_subject", "shared_material", "shared_technique"] as const;
const MEDIA_DECISIONS = [
  "approved_self_hosted",
  "external_link_only",
  "metadata_only",
  "metadata_only_after_automated_review",
  "blocked_source_unavailable",
  "blocked_rights_conflict",
] as const;

export type ArtConstellationLoadResult =
  | { status: "loaded"; release: ArtConstellationRelease; dataSource: ArtConstellationDataSource }
  | { status: "missing" | "incompatible" | "failed"; reason: string };

function requiredRecord(value: unknown, label: string): Record<string, unknown> {
  if (!isRecord(value)) throw new Error(`${label}_not_object`);
  return value;
}

function requiredString(value: unknown, label: string) {
  if (typeof value !== "string" || !value.trim()) throw new Error(`${label}_not_string`);
  return value.trim();
}

function optionalString(value: unknown) {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function hasControlCharacter(value: string) {
  return [...value].some((character) => {
    const code = character.charCodeAt(0);
    return code < 0x20 || code === 0x7f;
  });
}

function httpsUrl(value: string, label: string) {
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new Error(`${label}_invalid`);
  }
  if (
    url.protocol !== "https:" || !url.hostname || url.username || url.password ||
    hasControlCharacter(value)
  ) throw new Error(`${label}_not_https`);
  return url;
}

function hasCanonicalSourceId(sourceIds: string[], sourceName: string) {
  return sourceIds.some((sourceId) => {
    const [entityType, name, extra] = sourceId.split(":");
    return entityType === "source" && name === sourceName && extra === undefined;
  });
}

function artworkObjectUrl(value: unknown, artworkId: string, sourceIds: string[], releaseId: string) {
  const rawUrl = optionalString(value);
  if (!rawUrl) return null;
  const sourceOrigins: Record<string, string[]> = {
    aic_api: ["https://www.artic.edu", "https://api.artic.edu"],
    cleveland_open_access: ["https://clevelandart.org", "https://www.clevelandart.org"],
    met_open_access: ["https://www.metmuseum.org"],
    nga_open_data: ["https://www.nga.gov"],
    moma_open_data: ["https://www.moma.org"],
    tate_open_data: ["https://www.tate.org.uk"],
    cooper_hewitt_open_data: ["https://collection.cooperhewitt.org"],
    national_gallery_singapore: ["https://www.nationalgallery.sg"],
    vam_collections: ["https://collections.vam.ac.uk"],
    mia_open_access: ["https://collections.artsmia.org"],
    smithsonian_open_access: ["https://www.si.edu", "https://americanart.si.edu", "https://asia.si.edu"],
  };
  const expandedSourceNames = sourceIds.flatMap((sourceId) => {
    const [entityType, sourceName, extra] = sourceId.split(":");
    return entityType === "source" && extra === undefined && sourceOrigins[sourceName]
      ? [sourceName]
      : [];
  });
  const normalizedUrl = releaseId.startsWith("release:art-expansion-") && expandedSourceNames.length > 0 && rawUrl.startsWith("http://")
    ? `https://${rawUrl.slice("http://".length)}`
    : rawUrl;
  const url = httpsUrl(normalizedUrl, "artwork_official_object_url");
  const aicId = /^artwork:aic-(\d+)$/.exec(artworkId)?.[1];
  const metId = /^artwork:met-(\d+)$/.exec(artworkId)?.[1];
  const matchesAic = Boolean(
    aicId && hasCanonicalSourceId(sourceIds, "aic_api") && url.origin === "https://api.artic.edu" &&
    url.pathname === `/api/v1/artworks/${aicId}` && !url.search && !url.hash,
  );
  const matchesMet = Boolean(
    metId && hasCanonicalSourceId(sourceIds, "met_open_access") && url.origin === "https://www.metmuseum.org" &&
    url.pathname === `/art/collection/search/${metId}` && !url.search && !url.hash,
  );
  const isLegacyCanonicalArtwork = Boolean(aicId || metId);
  const matchesExpandedSource = !isLegacyCanonicalArtwork && expandedSourceNames.some(
    (sourceName) => sourceOrigins[sourceName]?.includes(url.origin),
  ) && url.pathname !== "/";
  if (!matchesAic && !matchesMet && !matchesExpandedSource) throw new Error("artwork_official_object_source_mismatch");
  return url.href;
}

function rightsRequestUrl(value: unknown, base: URL) {
  const rawUrl = requiredString(value, "rights_request_url");
  if (rawUrl.startsWith("//") || rawUrl.includes("\\") || hasControlCharacter(rawUrl)) {
    throw new Error("rights_request_url_invalid");
  }
  const hasScheme = /^[A-Za-z][A-Za-z0-9+.-]*:/.test(rawUrl);
  let url: URL;
  try {
    url = new URL(rawUrl, base);
  } catch {
    throw new Error("rights_request_url_invalid");
  }
  if (url.username || url.password) throw new Error("rights_request_url_invalid");
  if (!hasScheme) {
    if (url.origin !== base.origin || (url.protocol !== "http:" && url.protocol !== "https:")) {
      throw new Error("rights_request_url_not_same_origin");
    }
    return url.href;
  }
  if (
    url.protocol !== "https:" || url.hostname !== "github.com" || url.port ||
    url.pathname.replace(/\/$/, "") !== "/Archmays/Museum-Codex/issues/new"
  ) throw new Error("rights_request_url_not_approved");
  return url.href;
}

function requiredNumber(value: unknown, label: string) {
  if (typeof value !== "number" || !Number.isFinite(value)) throw new Error(`${label}_not_number`);
  return value;
}

function stringList(value: unknown, label: string) {
  if (!Array.isArray(value) || !value.every((item) => typeof item === "string" && item.length > 0)) {
    throw new Error(`${label}_not_string_list`);
  }
  return value as string[];
}

function objectList(value: unknown, label: string) {
  if (!Array.isArray(value) || !value.every(isRecord)) throw new Error(`${label}_not_object_list`);
  return value;
}

function localized(value: unknown, label: string): LocalizedText {
  if (typeof value === "string" && value.trim()) {
    return { "zh-Hans": value.trim(), en: value.trim() };
  }
  const record = requiredRecord(value, label);
  return {
    "zh-Hans": requiredString(record["zh-Hans"], `${label}_zh`),
    en: requiredString(record.en, `${label}_en`),
  };
}

function optionalLocalized(value: unknown, label: string): LocalizedText | null {
  return value === null || value === undefined ? null : localized(value, label);
}

export function publicNarrativeText(value: string) {
  return value
    .replace(/\breviewed\b/gi, "source-supported")
    .replace(/经审核的?/g, "有来源支持的");
}

function publicLocalized(value: unknown, label: string): LocalizedText {
  const parsed = localized(value, label);
  return {
    "zh-Hans": publicNarrativeText(parsed["zh-Hans"]),
    en: publicNarrativeText(parsed.en),
  };
}

function optionalPublicLocalized(value: unknown, label: string): LocalizedText | null {
  return value === null || value === undefined ? null : publicLocalized(value, label);
}

function assertEnvelope(root: Record<string, unknown>, releaseId: string, pluralKey: string) {
  if (root.schema_version !== ART_CONSTELLATION_SCHEMA_VERSION) throw new Error(`${pluralKey}_schema_version`);
  if (root.release_id !== releaseId) throw new Error(`${pluralKey}_release_id`);
  return objectList(root[pluralKey], pluralKey);
}

function aliasTexts(value: unknown) {
  if (!Array.isArray(value)) return [];
  return value.map((item) => {
    if (typeof item === "string") return requiredString(item, "alias");
    return requiredString(requiredRecord(item, "alias").text, "alias_text");
  });
}

function localizedItems(value: unknown, label: string) {
  return objectList(value, label).map((item) => localized(item.labels ?? item.label ?? item, `${label}_labels`));
}

function parseArtists(raw: unknown, releaseId: string): ArtistRecord[] {
  return assertEnvelope(requiredRecord(raw, "artists_root"), releaseId, "artists").map((artist) => {
    const isExpansionRelease = releaseId.startsWith("release:art-expansion-");
    const id = requiredString(artist.id, "artist_id");
    const artworkIds = stringList(artist.artwork_ids, "artist_artwork_ids");
    const places = objectList(artist.activity_places, "artist_activity_places");
    const periods = stringList(artist.historical_periods, "artist_periods");
    const traditions = stringList(artist.artistic_traditions, "artist_traditions");
    const lifeDates = requiredRecord(artist.life_dates, "artist_life_dates");
    const birth = requiredRecord(lifeDates.birth, "artist_birth");
    const death = requiredRecord(lifeDates.death, "artist_death");
    const review = requiredRecord(artist.review, "artist_review");
    const birthDisplay = requiredString(birth.display_value, "artist_birth_display");
    const deathDisplay = requiredString(death.display_value, "artist_death_display");
    const profileKind = artist.profile_kind === undefined && !isExpansionRelease
      ? "gallery"
      : requiredString(artist.profile_kind, "artist_profile_kind");
    if (profileKind !== "gallery" && profileKind !== "collection") throw new Error("artist_profile_kind_invalid");
    const successorNarratives = new Set([
      "release:art-expansion-batch-01-1.5.1",
      "release:art-expansion-batch-02-1.6.0",
    ]).has(releaseId);
    const publicIntro = artist.public_intro === undefined
      ? publicLocalized(artist.summary, "artist_summary")
      : publicLocalized(artist.public_intro, "artist_public_intro");
    if (successorNarratives && artist.public_intro === undefined) throw new Error("artist_public_intro_missing");
    const lookForRoot = artist.look_for === undefined ? null : requiredRecord(artist.look_for, "artist_look_for");
    const evidenceBoundary = artist.evidence_boundary === undefined
      ? publicLocalized(artist.summary, "artist_summary")
      : publicLocalized(artist.evidence_boundary, "artist_evidence_boundary");
    const sentenceProvenance = artist.sentence_provenance === undefined ? [] : objectList(artist.sentence_provenance, "artist_sentence_provenance").map((item) => ({
      sentenceId: requiredString(item.sentence_id, "artist_sentence_id"),
      text: publicLocalized(item.text, "artist_sentence_text"),
      claimIds: stringList(item.claim_ids, "artist_sentence_claim_ids"),
      evidenceIds: stringList(item.evidence_ids, "artist_sentence_evidence_ids"),
      sourceIds: stringList(item.source_ids, "artist_sentence_source_ids"),
    }));
    if (successorNarratives && sentenceProvenance.length < 2) throw new Error("artist_sentence_provenance_missing");
    const reading = artist.reading_profile === undefined ? null : requiredRecord(artist.reading_profile, "artist_reading_profile");
    const mediaProfile = reading ? requiredString(reading.media_profile, "artist_media_profile") : "metadata_only";
    if (!new Set(["self_hosted", "external_link_only", "metadata_only"]).has(mediaProfile)) throw new Error("artist_media_profile_invalid");
    return {
      id,
      publicSlug: artist.public_slug === undefined && !isExpansionRelease
        ? id.replace(/^artist:/, "")
        : requiredString(artist.public_slug, "artist_public_slug"),
      profileKind,
      sourceLanguageName: optionalString(artist.source_language_name),
      transliterations: artist.transliterations === undefined && !isExpansionRelease
        ? []
        : stringList(artist.transliterations, "artist_transliterations"),
      gallerySequence: artist.gallery_sequence === undefined && !isExpansionRelease
        ? artworkIds
        : stringList(artist.gallery_sequence, "artist_gallery_sequence"),
      labels: localized(artist.labels, "artist_labels"),
      summary: publicLocalized(artist.summary, "artist_summary"),
      publicIntro,
      lookFor: lookForRoot ? {
        "zh-Hans": stringList(lookForRoot["zh-Hans"], "artist_look_for_zh"),
        en: stringList(lookForRoot.en, "artist_look_for_en"),
      } : { "zh-Hans": [], en: [] },
      evidenceBoundary,
      sentenceProvenance,
      readingProfile: {
        mediaProfile: mediaProfile as "self_hosted" | "external_link_only" | "metadata_only",
        templateSignature: reading ? requiredString(reading.template_signature, "artist_template_signature") : "legacy-fallback",
      },
      aliases: aliasTexts(artist.aliases),
      period: requiredString(periods[0], "artist_period"),
      region: requiredString(places[0]?.label, "artist_region"),
      tradition: traditions[0] ?? null,
      lifeDisplay: { "zh-Hans": `${birthDisplay}—${deathDisplay}`, en: `${birthDisplay}–${deathDisplay}` },
      mediaPractice: localized(artist.media_practice, "artist_media_practice"),
      claimIds: stringList(artist.verified_claim_ids, "artist_claim_ids"),
      sourceIds: stringList(artist.source_ids, "artist_source_ids"),
      relationCount: requiredNumber(artist.relation_count, "artist_relation_count"),
      artworkIds,
      representativeMediaId: optionalString(artist.representative_media_id),
      approvedMediaArtworkCount: requiredNumber(
        artist.approved_media_artwork_count,
        "artist_approved_media_artwork_count",
      ),
      reviewer: requiredString(review.reviewer_id, "artist_reviewer"),
      reviewDate: requiredString(review.reviewed_at, "artist_review_date"),
    };
  });
}

function parseContexts(raw: unknown, releaseId: string): ContextRecord[] {
  return assertEnvelope(requiredRecord(raw, "contexts_root"), releaseId, "contexts").map((context) => ({
    id: requiredString(context.id, "context_id"),
    type: requiredString(context.context_type ?? context.type ?? context.entity_type, "context_type"),
    labels: localized(context.labels ?? context.label, "context_labels"),
  }));
}

function parseRelationships(raw: unknown, releaseId: string): RelationshipRecord[] {
  return assertEnvelope(requiredRecord(raw, "relationships_root"), releaseId, "relationships").map((relationship) => {
    const type = requiredString(relationship.type, "relationship_type") as RelationshipType;
    if (!RELATIONSHIP_TYPES.includes(type)) throw new Error("relationship_type_not_allowed");
    if (
      relationship.level !== "C" || relationship.directed !== false || relationship.is_algorithmic !== false ||
      relationship.historical_relationship_strength !== null || relationship.computational_similarity !== null
    ) {
      throw new Error("relationship_semantics_invalid");
    }
    const review = requiredRecord(relationship.review, "relationship_review");
    return {
      id: requiredString(relationship.id, "relationship_id"),
      sourceArtistId: requiredString(relationship.source_artist_id, "relationship_source"),
      targetArtistId: requiredString(relationship.target_artist_id, "relationship_target"),
      type,
      level: "C",
      title: localized(relationship.title, "relationship_title"),
      shortExplanation: publicLocalized(relationship.short_explanation, "relationship_short_explanation"),
      whatItMeans: publicLocalized(relationship.what_it_means, "relationship_what_it_means"),
      doesNotMean: publicLocalized(relationship.what_it_does_not_mean, "relationship_does_not_mean"),
      contextIds: stringList(relationship.context_ids, "relationship_context_ids"),
      supportingArtworkIds: stringList(relationship.supporting_artwork_ids, "relationship_artwork_ids"),
      evidenceConfidence: requiredNumber(relationship.evidence_confidence, "relationship_confidence"),
      curatorialRelevance: requiredNumber(relationship.curatorial_relevance, "relationship_relevance"),
      claimIds: stringList(relationship.claim_ids, "relationship_claim_ids"),
      evidenceIds: stringList(relationship.evidence_ids, "relationship_evidence_ids"),
      sourceIds: stringList(relationship.source_ids, "relationship_source_ids"),
      limitations: optionalPublicLocalized(relationship.limitations, "relationship_limitations"),
      reviewer: requiredString(review.reviewer_id, "relationship_reviewer"),
      reviewDate: requiredString(review.reviewed_at, "relationship_review_date"),
    };
  });
}

function parseArtworks(raw: unknown, releaseId: string): ArtworkRecord[] {
  return assertEnvelope(requiredRecord(raw, "artworks_root"), releaseId, "artworks").map((artwork) => {
    const id = requiredString(artwork.id, "artwork_id");
    const sourceIds = stringList(artwork.source_ids, "artwork_source_ids");
    const creation = requiredRecord(artwork.creation, "artwork_creation");
    const institution = requiredRecord(artwork.institution, "artwork_institution");
    const metadataLicense = requiredRecord(artwork.metadata_license, "artwork_metadata_license");
    const media = requiredRecord(artwork.media, "artwork_media");
    const decision = requiredString(media.decision, "artwork_media_decision") as ArtworkMediaDecision;
    if (!(MEDIA_DECISIONS as readonly string[]).includes(decision)) throw new Error("artwork_media_decision_invalid");
    const mediaIds = stringList(media.media_ids, "artwork_media_ids");
    const representativeMediaId = optionalString(media.representative_media_id);
    const approved = decision === "approved_self_hosted";
    if (
      (approved && (!representativeMediaId || mediaIds.length === 0 || !mediaIds.includes(representativeMediaId))) ||
      (!approved && (representativeMediaId !== null || mediaIds.length !== 0))
    ) throw new Error("artwork_media_decision_closure");
    const materials = localizedItems(artwork.materials, "artwork_materials");
    const techniques = localizedItems(artwork.techniques, "artwork_techniques");
    const mediumItems = [...materials, ...techniques];
    return {
      id,
      publicSlug: artwork.public_slug === undefined && !releaseId.startsWith("release:art-expansion-")
        ? id.replace(/^artwork:/, "").replaceAll(":", "-")
        : requiredString(artwork.public_slug, "artwork_public_slug"),
      artistId: requiredString(artwork.artist_id, "artwork_artist_id"),
      title: localized(artwork.labels, "artwork_title"),
      dateDisplay: optionalLocalized(creation.description, "artwork_creation_description"),
      mediumDisplay: mediumItems.length === 0 ? null : {
        "zh-Hans": mediumItems.map((item) => item["zh-Hans"]).join("、"),
        en: mediumItems.map((item) => item.en).join(", "),
      },
      institution: localized(institution.label, "artwork_institution_label"),
      objectUrl: artworkObjectUrl(artwork.official_object_url, id, sourceIds, releaseId),
      sourceIds,
      attribution: null,
      accessionNumber: optionalString(artwork.accession_number),
      materials,
      techniques,
      subjects: localizedItems(artwork.subjects, "artwork_subjects"),
      metadataLicense: requiredString(metadataLicense.rule_id, "artwork_metadata_license_rule"),
      limitations: optionalPublicLocalized(artwork.limitations, "artwork_limitations"),
      media: {
        decision,
        reasonCodes: stringList(media.reason_codes, "artwork_media_reason_codes"),
        representativeMediaId,
        mediaIds,
      },
    };
  });
}

function parseClaims(raw: unknown, releaseId: string): ClaimRecord[] {
  return assertEnvelope(requiredRecord(raw, "claims_root"), releaseId, "claims").map((claim) => {
    if (claim.status !== "publishable" || claim.publish_status !== "publishable") {
      throw new Error("claim_not_publishable");
    }
    const object = requiredRecord(claim.object, "claim_object");
    return {
      id: requiredString(claim.id, "claim_id"),
      subjectId: requiredString(claim.subject_id, "claim_subject_id"),
      predicate: requiredString(claim.predicate, "claim_predicate"),
      objectId: requiredString(object.entity_id ?? object.value, "claim_object_value"),
      evidenceIds: stringList(claim.evidence_ids, "claim_evidence_ids"),
      text: publicLocalized(claim.claim_text, "claim_text"),
    };
  });
}

function parseEvidence(raw: unknown, releaseId: string): EvidenceRecord[] {
  return assertEnvelope(requiredRecord(raw, "evidence_root"), releaseId, "evidence").map((evidence) => {
    const locator = requiredRecord(evidence.locator, "evidence_locator");
    return {
      id: requiredString(evidence.id, "evidence_id"),
      claimIds: stringList(evidence.claim_ids, "evidence_claim_ids"),
      sourceIds: stringList(evidence.source_ids, "evidence_source_ids"),
      summary: publicLocalized(evidence.summary, "evidence_summary"),
      locator: [optionalString(locator.record_id), optionalString(locator.section)].filter(Boolean).join(" · ") || null,
      reliabilityNote: publicLocalized(evidence.reliability_note, "evidence_reliability_note"),
    };
  });
}

function parseSources(raw: unknown, releaseId: string): SourceRecord[] {
  return assertEnvelope(requiredRecord(raw, "sources_root"), releaseId, "sources").map((source) => {
    const license = requiredRecord(source.license, "source_license");
    const identifiers = stringList(license.identifiers, "source_license_identifiers");
    const attributions = stringList(license.attribution_texts, "source_attribution_texts");
    const officialUrl = requiredString(source.official_url, "source_official_url");
    if (!/^https:\/\//i.test(officialUrl)) throw new Error("source_url_not_https");
    const locatorRecord = source.locator === null || source.locator === undefined
      ? null
      : requiredRecord(source.locator, "source_locator");
    if (locatorRecord) {
      const locatorUrl = requiredString(locatorRecord.url, "source_locator_url");
      if (locatorUrl !== officialUrl) throw new Error("source_locator_url_mismatch");
    }
    return {
      id: requiredString(source.id, "source_id"),
      title: requiredString(source.title, "source_title"),
      publisher: requiredString(source.publisher, "source_publisher"),
      officialUrl,
      date: optionalString(source.accessed_at),
      locator: locatorRecord ? localized(locatorRecord.label, "source_locator_label") : null,
      license: identifiers.join(", "),
      attribution: optionalString(source.attribution) ?? attributions.join(" · "),
    };
  });
}

function parseSearchEntries(raw: unknown, releaseId: string, artists: ArtistRecord[]): SearchEntry[] {
  const root = requiredRecord(raw, "search_index_root");
  if (root.schema_version !== ART_CONSTELLATION_SCHEMA_VERSION || root.release_id !== releaseId) {
    throw new Error("search_index_envelope");
  }
  const rawEntries = objectList(root.entries, "search_entries");
  if (rawEntries.length !== artists.length || rawEntries.some((entry) => entry.type !== "artist")) {
    throw new Error("search_artist_count");
  }
  return rawEntries.map((entry) => {
    const id = requiredString(entry.id, "search_entry_id");
    const artist = artists.find((candidate) => candidate.id === id);
    if (!artist) throw new Error("search_entry_unknown_artist");
    const normalizedKeys = objectList(entry.normalized_keys, "search_normalized_keys").map((key) =>
      requiredString(key.normalized_key, "search_normalized_key"),
    );
    return {
      id,
      labels: localized(entry.labels, "search_entry_labels"),
      aliases: aliasTexts(entry.aliases),
      normalizedKeys: [...new Set(normalizedKeys)],
    };
  });
}

function parseLayout(raw: unknown, releaseId: string): LayoutNode[] {
  const root = requiredRecord(raw, "layout_root");
  if (root.schema_version !== ART_CONSTELLATION_SCHEMA_VERSION || root.release_id !== releaseId) throw new Error("layout_contract");
  if (root.algorithm === "focused_relation_lanes_v1") {
    if (objectList(root.default_nodes, "layout_default_nodes").length !== 0) throw new Error("layout_default_nodes");
    return [];
  }
  if (root.algorithm !== "deterministic_circle_v1" || root.seed !== "museum-04-art-constellation-1.0.0") throw new Error("layout_contract");
  return objectList(root.nodes, "layout_nodes").map((node) => ({
    artistId: requiredString(node.artist_id, "layout_artist_id"),
    x: requiredNumber(node.x, "layout_x"),
    y: requiredNumber(node.y, "layout_y"),
  }));
}

function parseExplorerConfig(raw: unknown, releaseId: string, artists: ArtistRecord[]): RelationshipExplorerConfig {
  if (raw === null) {
    return {
      algorithm: "legacy_circle_fallback",
      defaultGlobalGraphNodeCount: artists.length,
      focusInitialNeighborLimit: 12,
      focusInitialPerLaneLimit: 4,
      focusExpandedNodeLimit: 20,
      themeVisualArtistLimit: 16,
      themeTextPageSize: 16,
      laneOrder: [...RELATIONSHIP_TYPES],
      starterArtistIds: artists.slice(0, 9).map((artist) => artist.id),
      semantics: { "zh-Hans": "策展比较不代表历史影响。", en: "Curatorial comparison does not imply historical influence." },
    };
  }
  const root = requiredRecord(raw, "relationship_explorer_config");
  if (
    root.schema_version !== ART_CONSTELLATION_SCHEMA_VERSION || root.release_id !== releaseId ||
    root.algorithm !== "focused_relation_lanes_v1" || requiredNumber(root.default_global_graph_node_count, "default_graph_nodes") !== 0
  ) throw new Error("relationship_explorer_config_invalid");
  const laneOrder = stringList(root.lane_order, "explorer_lane_order") as RelationshipType[];
  if (laneOrder.length !== 3 || laneOrder.some((type) => !RELATIONSHIP_TYPES.includes(type))) throw new Error("explorer_lane_order");
  const starterRotation = requiredRecord(root.starter_rotation, "starter_rotation");
  const starterArtistIds = stringList(starterRotation.artist_ids, "starter_artist_ids");
  const artistIds = new Set(artists.map((artist) => artist.id));
  if (starterArtistIds.length > 9 || starterArtistIds.some((id) => !artistIds.has(id))) throw new Error("starter_artist_ids");
  return {
    algorithm: "focused_relation_lanes_v1",
    defaultGlobalGraphNodeCount: 0,
    focusInitialNeighborLimit: requiredNumber(root.focus_initial_neighbor_limit, "focus_initial_neighbor_limit"),
    focusInitialPerLaneLimit: requiredNumber(root.focus_initial_per_lane_limit, "focus_initial_per_lane_limit"),
    focusExpandedNodeLimit: requiredNumber(root.focus_expanded_node_limit, "focus_expanded_node_limit"),
    themeVisualArtistLimit: requiredNumber(root.theme_visual_artist_limit, "theme_visual_artist_limit"),
    themeTextPageSize: requiredNumber(root.theme_text_page_size, "theme_text_page_size"),
    laneOrder,
    starterArtistIds,
    semantics: publicLocalized(root.semantics, "explorer_semantics"),
  };
}

function facetValues(value: unknown, label: string) {
  return objectList(value, label).map((item) => requiredString(item.value, `${label}_value`));
}

function compactFacetValues(value: unknown, label: string) {
  const values = stringList(value, label);
  if (values.length !== new Set(values).size || values.some((item) => !item.trim())) {
    throw new Error(`${label}_invalid`);
  }
  return values;
}

function parseFacets(raw: unknown, releaseId: string) {
  const root = requiredRecord(raw, "facets_root");
  if (root.schema_version !== ART_CONSTELLATION_SCHEMA_VERSION || root.release_id !== releaseId) {
    throw new Error("facets_envelope");
  }
  const compact = root.facets === undefined;
  const facets = compact ? root : requiredRecord(root.facets, "facets");
  const values = compact ? compactFacetValues : facetValues;
  const relationshipTypes = values(facets.relationship_types, "relationship_type_facets") as RelationshipType[];
  if (relationshipTypes.some((type) => !RELATIONSHIP_TYPES.includes(type))) throw new Error("facet_relationship_type");
  return {
    periods: values(facets.periods, "period_facets"),
    regions: values(facets.regions, "region_facets"),
    traditions: values(facets.traditions, "tradition_facets"),
    relationshipTypes,
  };
}

function parseRights(raw: unknown, releaseId: string, base: URL): RightsRecord {
  const root = requiredRecord(raw, "rights_root");
  if (root.schema_version !== ART_CONSTELLATION_SCHEMA_VERSION || root.release_id !== releaseId) {
    throw new Error("rights_envelope");
  }
  const code = requiredRecord(root.code_rights, "code_rights");
  const content = requiredRecord(root.original_content_rights, "content_rights");
  const metadata = requiredRecord(root.third_party_metadata, "third_party_metadata");
  const media = requiredRecord(root.media, "media_rights");
  const request = requiredRecord(root.rights_request, "rights_request");
  const mediaCount = requiredNumber(media.count, "media_count");
  const mediaBytes = requiredNumber(media.bytes, "media_bytes");
  const approvedMediaArtworks = requiredNumber(media.approved_artworks, "approved_media_artworks");
  const noImageArtworks = requiredNumber(media.no_image_artworks, "no_image_artworks");
  const mediaBundleHash = requiredString(media.media_bundle_hash, "media_bundle_hash");
  if (
    code.identifier !== "ALL-RIGHTS-RESERVED" || code.status !== "decided" ||
    content.identifier !== "ALL-RIGHTS-RESERVED" || content.status !== "decided" ||
    ![mediaCount, mediaBytes, approvedMediaArtworks, noImageArtworks].every(
      (value) => Number.isInteger(value) && value >= 0,
    ) ||
    media.external_runtime_count !== 0 || media.blocked_asset_count !== 0 ||
    !/^sha256:[a-f0-9]{64}$/.test(mediaBundleHash)
  ) throw new Error("rights_profile_invalid");
  return {
    codeRights: localized(code.statement, "code_rights_statement"),
    originalContentRights: localized(content.statement, "content_rights_statement"),
    thirdPartyMetadata: [localized(metadata.statement, "metadata_rights_statement")],
    mediaStatement: localized(media.statement, "media_rights_statement"),
    mediaCount,
    mediaBytes,
    approvedMediaArtworks,
    noImageArtworks,
    mediaBundleId: requiredString(media.media_bundle_id, "media_bundle_id"),
    mediaBundleHash,
    rightsRequestUrl: rightsRequestUrl(request.url, base),
    noticesPath: requiredString(media.notices_path ?? metadata.notices_path, "notices_path"),
    attributionsPath: requiredString(media.attributions_path ?? root.attributions_path, "attributions_path"),
    withdrawalPath: requiredString(media.withdrawal_path, "withdrawal_path"),
  };
}

function parseGraphSummary(raw: unknown, releaseId: string) {
  const root = requiredRecord(raw, "graph_summary_root");
  if (
    root.schema_version !== ART_CONSTELLATION_SCHEMA_VERSION || root.release_id !== releaseId ||
    root.profile !== "media_aware"
  ) throw new Error("graph_summary_envelope");
  const counts = requiredRecord(root.counts, "graph_counts");
  const levels = requiredRecord(counts.levels, "graph_level_counts");
  const relationTypes = requiredRecord(counts.relationship_types, "graph_relationship_type_counts");
  const semantics = requiredRecord(root.semantics, "graph_semantics");
  const initialState = requiredRecord(root.initial_state, "graph_initial_state");
  const artistCount = requiredNumber(counts.artists, "artist_count");
  const contextCount = requiredNumber(counts.contexts, "context_count");
  const relationshipCount = requiredNumber(counts.relationships, "relationship_count");
  const artworkCount = requiredNumber(counts.artworks, "artwork_count");
  const mediaCount = requiredNumber(counts.media, "media_count");
  const mediaBytes = requiredNumber(counts.media_bytes, "media_bytes");
  const approvedMediaArtworkCount = requiredNumber(counts.approved_media_artworks, "approved_media_artworks");
  const noImageArtworkCount = requiredNumber(counts.no_image_artworks, "no_image_artworks");
  const mediaParentCount = requiredNumber(counts.media_provenance_parents, "media_provenance_parents");
  const levelCounts = {
    A: requiredNumber(levels.A, "level_a_count"),
    B: requiredNumber(levels.B, "level_b_count"),
    C: requiredNumber(levels.C, "level_c_count"),
  };
  const relationshipTypeCounts = {
    shared_subject: requiredNumber(relationTypes.shared_subject, "shared_subject_count"),
    shared_material: requiredNumber(relationTypes.shared_material, "shared_material_count"),
    shared_technique: requiredNumber(relationTypes.shared_technique, "shared_technique_count"),
  };
  const numericCounts = [
    artistCount, contextCount, relationshipCount, artworkCount, mediaCount, mediaBytes,
    approvedMediaArtworkCount, noImageArtworkCount, mediaParentCount,
    ...Object.values(levelCounts), ...Object.values(relationshipTypeCounts),
  ];
  if (
    numericCounts.some((value) => !Number.isInteger(value) || value < 0) ||
    artistCount === 0 || artworkCount !== approvedMediaArtworkCount + noImageArtworkCount ||
    (approvedMediaArtworkCount === 0
      ? mediaParentCount !== 0
      : mediaParentCount <= 0 || mediaParentCount > approvedMediaArtworkCount) ||
    Object.values(levelCounts).reduce((sum, value) => sum + value, 0) !== relationshipCount ||
    Object.values(relationshipTypeCounts).reduce((sum, value) => sum + value, 0) !== relationshipCount ||
    semantics.algorithmic !== false || semantics.causal !== false || semantics.directed !== false ||
    initialState.view !== "graph" || initialState.edges_visible !== false || initialState.focused_artist_id !== null ||
    (new Set([
      "release:art-expansion-batch-01-1.5.1",
      "release:art-expansion-batch-02-1.6.0",
    ]).has(releaseId) && initialState.task !== "choose_artist")
  ) throw new Error("graph_summary_profile_invalid");
  const summary: GraphSummary = {
    releaseId,
    title: localized(root.title, "graph_title"),
    artistCount,
    contextCount,
    relationshipCount,
    artworkCount,
    mediaCount,
    mediaBytes,
    approvedMediaArtworkCount,
    noImageArtworkCount,
    levelCounts,
    relationshipTypeCounts,
    semantics: localized(semantics.what_it_does_not_mean, "graph_semantics_notice"),
    initialState: "artists_only",
  };
  return { summary, artifactPaths: requiredRecord(root.artifact_paths, "graph_artifact_paths") };
}

type MediaIndexAsset = Omit<
  MediaAsset,
  | "attribution"
  | "changesStatement"
  | "licenseIdentifier"
  | "licenseUrl"
  | "sourceUrl"
  | "withdrawalStatus"
  | "withdrawalNotice"
>;

function exactPositiveInteger(value: unknown, label: string) {
  const number = requiredNumber(value, label);
  if (!Number.isInteger(number) || number <= 0) throw new Error(`${label}_not_positive_integer`);
  return number;
}

function releaseAssetUrl(path: string, base: URL) {
  const isReleaseChild = /^assets\/[a-z0-9._-]+\/[0-9]+w\.(?:jpg|webp)$/i.test(path);
  const isSiteReleaseAsset = /^releases\/[a-z0-9._-]+\/assets\/(?:[a-z0-9._-]+\/[0-9]+w|sha256\/[a-f0-9]{2}\/[a-f0-9]{64})\.(?:jpg|webp)$/i.test(path);
  if (!SAFE_PATH.test(path) || (!isReleaseChild && !isSiteReleaseAsset)) {
    throw new Error("media_src_not_release_child");
  }
  const siteBase = new URL(import.meta.env.BASE_URL, base.origin);
  const url = new URL(path, isSiteReleaseAsset ? siteBase : base);
  const basePath = base.pathname.endsWith("/") ? base.pathname : `${base.pathname}/`;
  const siteBasePath = siteBase.pathname.endsWith("/") ? siteBase.pathname : `${siteBase.pathname}/`;
  if (
    url.origin !== base.origin ||
    (isReleaseChild && !url.pathname.startsWith(`${basePath}assets/`)) ||
    (isSiteReleaseAsset && !url.pathname.startsWith(`${siteBasePath}releases/`))
  ) {
    throw new Error("media_src_not_same_origin_release_child");
  }
  return url.href;
}

function parseMediaSupport(
  mediaRaw: unknown,
  attributionsRaw: unknown,
  withdrawalRaw: unknown,
  releaseId: string,
  base: URL,
  artworks: ArtworkRecord[],
  manifest: ReleaseManifest,
  artifactFiles: Map<string, RuntimeAssetFile>,
): MediaAsset[] {
  const root = requiredRecord(mediaRaw, "media_index_root");
  const mediaBundleHash = requiredString(root.media_bundle_hash, "media_bundle_hash");
  if (
    root.schema_version !== ART_CONSTELLATION_SCHEMA_VERSION || root.release_id !== releaseId ||
    !/^sha256:[a-f0-9]{64}$/.test(mediaBundleHash)
  ) throw new Error("media_index_envelope");
  const delivery = requiredRecord(root.delivery_policy, "media_delivery_policy");
  const counts = requiredRecord(root.counts, "media_counts");
  const approvedArtworkCount = requiredNumber(counts.approved_artworks, "approved_artwork_count");
  const noImageArtworkCount = requiredNumber(counts.no_image_artworks, "no_image_artwork_count");
  const assetCount = requiredNumber(counts.assets, "media_asset_count");
  const byteCount = requiredNumber(counts.bytes, "media_byte_count");
  if (
    delivery.external_runtime_api !== false || delivery.external_delivery_count !== 0 ||
    delivery.blocked_asset_count !== 0 || delivery.preferred !== "self_hosted" ||
    delivery.low_bandwidth_default !== "metadata_only" ||
    ![approvedArtworkCount, noImageArtworkCount, assetCount, byteCount].every(
      (value) => Number.isInteger(value) && value >= 0,
    ) ||
    approvedArtworkCount + noImageArtworkCount !== artworks.length
  ) throw new Error("media_delivery_profile_invalid");

  const artworkById = new Map(artworks.map((artwork) => [artwork.id, artwork]));
  const mediaArtworkRecords = objectList(root.artworks, "media_index_artworks");
  if (mediaArtworkRecords.length !== artworks.length || artworkById.size !== artworks.length) {
    throw new Error("media_artwork_count");
  }
  for (const item of mediaArtworkRecords) {
    const artworkId = requiredString(item.artwork_id, "media_artwork_id");
    const artwork = artworkById.get(artworkId);
    if (!artwork) throw new Error("media_index_unknown_artwork");
    const decision = requiredString(item.decision, "media_artwork_decision");
    const mediaIds = stringList(item.media_ids, "media_artwork_media_ids");
    if (
      decision !== artwork.media.decision ||
      optionalString(item.representative_media_id) !== artwork.media.representativeMediaId ||
      !sameSet(mediaIds, artwork.media.mediaIds) ||
      !sameSet(stringList(item.reason_codes, "media_artwork_reason_codes"), artwork.media.reasonCodes)
    ) throw new Error("media_artwork_projection_mismatch");
  }
  if (
    artworks.filter((artwork) => artwork.media.decision === "approved_self_hosted").length !== approvedArtworkCount ||
    artworks.filter((artwork) => artwork.media.decision !== "approved_self_hosted").length !== noImageArtworkCount
  ) throw new Error("media_artwork_decision_counts");

  const assets: MediaIndexAsset[] = objectList(root.assets, "media_assets").map((item) => {
    const id = requiredString(item.id, "media_id");
    const artworkId = requiredString(item.artwork_id, "media_artwork_id");
    const publicPath = requiredString(item.src, "media_src");
    const format = requiredString(item.format, "media_format");
    const mimeType = requiredString(item.mime_type, "media_mime_type");
    const role = requiredString(item.role, "media_role");
    if (
      !artworkById.has(artworkId) || !["jpeg", "webp"].includes(format) ||
      !["image/jpeg", "image/webp"].includes(mimeType) ||
      (format === "jpeg" ? mimeType !== "image/jpeg" || !publicPath.endsWith(".jpg") : mimeType !== "image/webp" || !publicPath.endsWith(".webp")) ||
      !["thumbnail", "detail", "zoom"].includes(role)
    ) throw new Error("media_asset_profile_invalid");
    const width = exactPositiveInteger(item.width, "media_width");
    const height = exactPositiveInteger(item.height, "media_height");
    const bytes = exactPositiveInteger(item.bytes, "media_bytes");
    const sha256 = requiredString(item.sha256, "media_sha256");
    if (!/^sha256:[a-f0-9]{64}$/.test(sha256)) throw new Error("media_sha256_invalid");
    const manifestFile = artifactFiles.get(publicPath);
    if (
      !manifestFile || manifestFile.record_type !== "media" ||
      manifestFile.sha256.replace(/^sha256:/, "") !== sha256.replace(/^sha256:/, "") ||
      manifestFile.bytes !== bytes || !manifestFile.record_ids.includes(id)
    ) throw new Error("media_asset_manifest_closure");
    return {
      id,
      artworkId,
      parentMediaId: requiredString(item.parent_media_id, "media_parent_id"),
      src: releaseAssetUrl(publicPath, base),
      publicPath,
      format: format as MediaIndexAsset["format"],
      mimeType: mimeType as MediaIndexAsset["mimeType"],
      width,
      height,
      bytes,
      sha256,
      role: role as MediaIndexAsset["role"],
    };
  });
  const assetIds = assets.map((asset) => asset.id);
  if (
    assets.length !== assetCount || new Set(assetIds).size !== assetCount ||
    assets.reduce((sum, asset) => sum + asset.bytes, 0) !== byteCount ||
    assetIds.some((id) => !manifest.attribution_manifest.asset_ids.includes(id)) ||
    assetIds.some((id) => !manifest.included_media_asset_ids.includes(id))
  ) throw new Error("media_asset_count_or_manifest_ids");

  for (const artwork of artworks) {
    const ids = assets.filter((asset) => asset.artworkId === artwork.id).map((asset) => asset.id);
    if (!sameSet(ids, artwork.media.mediaIds)) throw new Error("artwork_media_asset_closure");
  }

  const attributionRoot = requiredRecord(attributionsRaw, "attributions_root");
  const rawAttributions = objectList(attributionRoot.assets, "attribution_assets");
  const rawAttributionIds = rawAttributions.map((item) => requiredString(item.asset_id, "attribution_asset_id"));
  if (
    rawAttributions.length !== manifest.attribution_manifest.asset_ids.length ||
    new Set(rawAttributionIds).size !== rawAttributions.length ||
    !sameSet(rawAttributionIds, manifest.attribution_manifest.asset_ids)
  ) throw new Error("media_attribution_manifest_closure");
  const childIdSet = new Set(assetIds);
  const attributions = new Map(rawAttributions.filter((item) => childIdSet.has(String(item.asset_id))).map((item) => {
    const id = requiredString(item.asset_id, "attribution_asset_id");
    const licenseUrl = requiredString(item.license_url, "attribution_license_url");
    const sourceUrl = requiredString(item.source_url, "attribution_source_url");
    if (!/^https:\/\//i.test(licenseUrl) || !/^https:\/\//i.test(sourceUrl)) throw new Error("attribution_url_not_https");
    return [id, {
      attribution: requiredString(item.attribution, "media_attribution"),
      changesStatement: requiredString(item.changes_statement, "media_changes_statement"),
      licenseIdentifier: requiredString(item.license_identifier, "media_license_identifier"),
      licenseUrl,
      sourceUrl,
    }] as const;
  }));
  const withdrawalRoot = requiredRecord(withdrawalRaw, "withdrawal_root");
  const withdrawals = new Map(objectList(withdrawalRoot.mappings, "withdrawal_mappings").map((item) => {
    const id = requiredString(item.media_id, "withdrawal_media_id");
    if (item.status !== "active") throw new Error("withdrawal_media_not_active");
    return [id, {
      artworkId: requiredString(item.artwork_id, "withdrawal_artwork_id"),
      paths: stringList(item.derivative_paths, "withdrawal_paths"),
      notice: requiredString(item.public_notice, "withdrawal_notice"),
    }] as const;
  }));
  if (
    attributions.size !== assets.length || withdrawals.size !== assets.length ||
    assets.some((asset) => !attributions.has(asset.id) || !withdrawals.has(asset.id))
  ) throw new Error("media_rights_record_count");

  return assets.map((asset) => {
    const attribution = attributions.get(asset.id);
    const withdrawal = withdrawals.get(asset.id);
    const predecessorRelativePath = /^releases\/[a-z0-9._-]+\/(assets\/.*)$/i.exec(asset.publicPath)?.[1] ?? null;
    if (
      !attribution || !withdrawal || withdrawal.artworkId !== asset.artworkId ||
      !withdrawal.paths.includes(asset.publicPath) &&
      (!predecessorRelativePath || !withdrawal.paths.includes(predecessorRelativePath))
    ) throw new Error("media_rights_reference_closure");
    return {
      ...asset,
      ...attribution,
      withdrawalStatus: "active" as const,
      withdrawalNotice: publicNarrativeText(withdrawal.notice),
    };
  });
}

async function digestHex(bytes: ArrayBuffer) {
  if (!globalThis.crypto?.subtle) throw new Error("web_crypto_unavailable");
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function fetchVerifiedJson(
  url: string,
  expectedHash: string,
  fetcher: typeof fetch,
  signal?: AbortSignal,
) {
  const response = await fetchJsonBytes(url, fetcher, signal);
  if (!response.ok) throw new Error(`artifact_http_${response.status}`);
  const bytes = response.bytes;
  if ((await digestHex(bytes)) !== expectedHash.replace(/^sha256:/, "")) throw new Error("artifact_hash_mismatch");
  return JSON.parse(new TextDecoder().decode(bytes)) as unknown;
}

function parseAssetResolutionManifest(raw: unknown, manifest: ReleaseManifest): AssetResolutionManifest {
  const value = requiredRecord(raw, "asset_resolution_root");
  const referencedFiles = value.referenced_files;
  const materializedFiles = value.materialized_asset_files;
  if (
    !Array.isArray(referencedFiles) || !referencedFiles.every(isRuntimeAssetFile) ||
    !Array.isArray(materializedFiles) || !materializedFiles.every(isRuntimeAssetFile)
  ) throw new Error("asset_resolution_files_invalid");
  const allFiles = [...referencedFiles, ...materializedFiles];
  const paths = allFiles.map((file) => file.path);
  if (
    requiredString(value.id, "asset_resolution_id") !== `asset-resolution:art-expansion-${manifest.version}` ||
    requiredString(value.schema_version, "asset_resolution_schema_version") !== "1.0.0" ||
    requiredString(value.release_id, "asset_resolution_release_id") !== manifest.id ||
    !/^sha256:[a-f0-9]{64}$/.test(requiredString(value.content_hash, "asset_resolution_content_hash")) ||
    value.referenced_file_count !== referencedFiles.length ||
    value.materialized_asset_count !== materializedFiles.length ||
    value.new_public_original_count !== 0 ||
    value.runtime_external_image_request_count !== 0 ||
    new Set(paths).size !== paths.length ||
    materializedFiles.some((file) => file.record_type !== "media" || file.delivery_mode !== "build_materialized")
  ) throw new Error("asset_resolution_closure_invalid");
  const mediaRecordIds = new Set(allFiles.filter((file) => file.record_type === "media").flatMap((file) => file.record_ids));
  if (
    mediaRecordIds.size !== manifest.included_media_asset_ids.length ||
    manifest.included_media_asset_ids.some((id) => !mediaRecordIds.has(id))
  ) throw new Error("asset_resolution_media_closure_invalid");
  return value as AssetResolutionManifest;
}

async function assetResolutionContentHash(files: RuntimeAssetFile[]) {
  const lines = [...files]
    .sort((left, right) => left.path.localeCompare(right.path))
    .map((file) => `${file.path}\0${file.sha256}\0${file.bytes}\n`)
    .join("");
  return `sha256:${await digestHex(new TextEncoder().encode(lines).buffer)}`;
}

export async function loadAssetResolutionManifest(
  base: URL,
  manifest: ReleaseManifest,
  fetcher: typeof fetch = fetch,
  signal?: AbortSignal,
) {
  const reference = manifest.manifest_files.find((file) => file.path === "asset-resolution-manifest.json");
  if (!reference || reference.record_type !== "other") throw new Error("asset_resolution_manifest_missing");
  const resolution = parseAssetResolutionManifest(
    await fetchVerifiedJson(new URL(reference.path, base).href, reference.sha256, fetcher, signal),
    manifest,
  );
  const computed = await assetResolutionContentHash([
    ...resolution.referenced_files,
    ...resolution.materialized_asset_files,
  ]);
  if (computed !== resolution.content_hash) throw new Error("asset_resolution_content_hash_mismatch");
  return resolution;
}

function assertSameOrigin(baseUrl: string) {
  const documentUrl = typeof window === "undefined" ? "https://museum-codex.invalid/" : window.location.href;
  const base = new URL(baseUrl, documentUrl);
  if (typeof window !== "undefined" && base.origin !== window.location.origin) throw new Error("release_cross_origin");
  return base;
}

function expectedReleaseIdFromBase(base: URL) {
  const segments = base.pathname.split("/").filter(Boolean);
  const directory = segments.at(-1);
  if (!directory || !/^[a-z0-9][a-z0-9._-]*$/.test(directory)) {
    throw new Error("release_directory_invalid");
  }
  return `release:${directory}`;
}

function assertInitialClosure(release: ArtConstellationRelease) {
  const artistIds = new Set(release.artists.map((artist) => artist.id));
  if (
    artistIds.size !== release.summary.artistCount ||
    release.layout.length !== release.explorerConfig.defaultGlobalGraphNodeCount ||
    release.searchEntries.length !== release.summary.artistCount
  ) throw new Error("release_counts_invalid");
  if (
    new Set(release.layout.map((node) => node.artistId)).size !== release.explorerConfig.defaultGlobalGraphNodeCount ||
    release.layout.some((node) => !artistIds.has(node.artistId))
  ) {
    throw new Error("layout_artist_closure");
  }
  if (
    new Set(release.searchEntries.map((entry) => entry.id)).size !== release.summary.artistCount ||
    release.searchEntries.some((entry) => !artistIds.has(entry.id))
  ) throw new Error("search_artist_closure");
}

function assertArtistArtworkClosure(
  release: ArtConstellationRelease,
  artworks: ArtworkRecord[],
  media: MediaAsset[],
) {
  const artistIds = new Set(release.artists.map((artist) => artist.id));
  const artworkIds = new Set(artworks.map((artwork) => artwork.id));
  if (
    artworks.length !== release.summary.artworkCount ||
    artworkIds.size !== release.summary.artworkCount ||
    media.length !== release.summary.mediaCount ||
    artworks.some((artwork) => !artistIds.has(artwork.artistId))
  ) {
    throw new Error("artist_artwork_counts_invalid");
  }
  for (const artist of release.artists) {
    const ownedArtworkIds = artworks.filter((artwork) => artwork.artistId === artist.id).map((artwork) => artwork.id);
    const approvedCount = artworks.filter(
      (artwork) => artwork.artistId === artist.id && artwork.media.decision === "approved_self_hosted",
    ).length;
    const representative = artist.representativeMediaId
      ? media.find((asset) => asset.id === artist.representativeMediaId)
      : null;
    if (
      !sameSet(ownedArtworkIds, artist.artworkIds) || approvedCount !== artist.approvedMediaArtworkCount ||
      (artist.representativeMediaId !== null && (!representative || !ownedArtworkIds.includes(representative.artworkId))) ||
      (approvedCount === 0 && artist.representativeMediaId !== null) ||
      (approvedCount > 0 && artist.representativeMediaId === null)
    ) throw new Error("artist_artwork_media_projection_invalid");
  }
}

function assertRelationshipIndexClosure(release: ArtConstellationRelease, index: RelationshipIndex) {
  const artistIds = new Set(release.artists.map((artist) => artist.id));
  const contextIds = new Set(index.contexts.map((context) => context.id));
  if (contextIds.size !== release.summary.contextCount || index.relationships.length !== release.summary.relationshipCount) {
    throw new Error("relationship_index_counts_invalid");
  }
  const seenTypes: Record<RelationshipType, number> = {
    shared_subject: 0,
    shared_material: 0,
    shared_technique: 0,
  };
  const connectedArtists = new Set<string>();
  const relationshipCounts = new Map(release.artists.map((artist) => [artist.id, 0]));
  for (const relationship of index.relationships) {
    if (
      !artistIds.has(relationship.sourceArtistId) || !artistIds.has(relationship.targetArtistId) ||
      relationship.sourceArtistId === relationship.targetArtistId ||
      relationship.contextIds.some((id) => !contextIds.has(id))
    ) throw new Error("relationship_reference_closure");
    seenTypes[relationship.type] += 1;
    connectedArtists.add(relationship.sourceArtistId);
    connectedArtists.add(relationship.targetArtistId);
    relationshipCounts.set(relationship.sourceArtistId, (relationshipCounts.get(relationship.sourceArtistId) ?? 0) + 1);
    relationshipCounts.set(relationship.targetArtistId, (relationshipCounts.get(relationship.targetArtistId) ?? 0) + 1);
  }
  const expectedConnectedArtists = release.artists.filter((artist) => artist.relationCount > 0).map((artist) => artist.id);
  if (
    !sameSet([...connectedArtists], expectedConnectedArtists) ||
    release.artists.some((artist) => relationshipCounts.get(artist.id) !== artist.relationCount) ||
    RELATIONSHIP_TYPES.some((type) => seenTypes[type] !== release.summary.relationshipTypeCounts[type])
  ) throw new Error("relationship_index_semantics_invalid");
}

function assertDetailClosure(
  relationship: RelationshipRecord,
  artworks: ArtworkRecord[],
  evidence: EvidenceRecord[],
  sources: SourceRecord[],
) {
  const artworkIds = new Set(artworks.map((artwork) => artwork.id));
  const evidenceIds = new Set(evidence.map((item) => item.id));
  const sourceIds = new Set(sources.map((source) => source.id));
  if (
    relationship.supportingArtworkIds.some((id) => !artworkIds.has(id)) ||
    relationship.evidenceIds.some((id) => !evidenceIds.has(id)) ||
    relationship.sourceIds.some((id) => !sourceIds.has(id)) ||
    artworks.some((artwork) => artwork.sourceIds.some((id) => !sourceIds.has(id))) ||
    evidence.some((item) => item.sourceIds.some((id) => !sourceIds.has(id)))
  ) throw new Error("relationship_detail_reference_closure");
}

function parseNotices(raw: unknown): ThirdPartyNotice[] {
  const root = requiredRecord(raw, "notices_root");
  return objectList(root.notices, "notices").map((notice) => {
    const sourceUrl = optionalString(notice.source_url);
    if (sourceUrl && !/^https:\/\//i.test(sourceUrl)) throw new Error("notice_url_not_https");
    return {
      id: requiredString(notice.record_id, "notice_record_id"),
      notice: optionalString(notice.notice) ?? [
        ...stringList(notice.attribution_texts ?? [], "notice_attributions"),
        optionalString(notice.rights_holder),
      ].filter(Boolean).join(" · "),
      sourceUrl,
      licenseIdentifiers: stringList(notice.license_identifiers ?? [], "notice_license_identifiers"),
      attributions: stringList(notice.attribution_texts ?? [], "notice_attributions"),
    };
  });
}

function assertRightsSupportArtifacts(
  sourceRegistryRaw: unknown,
  licenseDecisionsRaw: unknown,
  attributionsRaw: unknown,
  manifest: ReleaseManifest,
) {
  const sourceRegistry = requiredRecord(sourceRegistryRaw, "source_registry_root");
  if (sourceRegistry.schema_version !== ART_CONSTELLATION_SCHEMA_VERSION) throw new Error("source_registry_schema_version");
  const registrySourceIds = objectList(sourceRegistry.sources, "source_registry_sources").map((source) =>
    requiredString(source.source_id, "source_registry_source_id"),
  );
  if (!sameSet(registrySourceIds, manifest.included_source_ids)) throw new Error("source_registry_release_closure");

  const licenseDecisions = requiredRecord(licenseDecisionsRaw, "license_decisions_root");
  if (licenseDecisions.schema_version !== ART_CONSTELLATION_SCHEMA_VERSION) throw new Error("license_decisions_schema_version");
  const decisions = objectList(licenseDecisions.decisions, "license_decisions");
  for (const decisionId of [
    manifest.license_decisions.code_license_decision_id,
    manifest.license_decisions.original_content_license_decision_id,
  ]) {
    const decision = decisions.find((candidate) => candidate.decision_id === decisionId);
    if (!decision || decision.status !== "decided") throw new Error("license_decision_incomplete");
    const license = requiredRecord(decision.license, "license_decision_license");
    if (license.identifier !== "ALL-RIGHTS-RESERVED") throw new Error("license_decision_not_rights_reserved");
  }

  const attributions = requiredRecord(attributionsRaw, "attributions_root");
  const attributedIds = objectList(attributions.assets, "attribution_assets").map((asset) =>
    requiredString(asset.asset_id, "attribution_asset_id"),
  );
  if (!sameSet(attributedIds, manifest.attribution_manifest.asset_ids)) {
    throw new Error("media_attribution_manifest_mismatch");
  }
}

async function detailResult<T>(
  operation: () => Promise<T>,
  signal?: AbortSignal,
): Promise<DetailLoadResult<T>> {
  try {
    return { status: "loaded", data: await operation() };
  } catch (error) {
    if (signal?.aborted) return { status: "failed", reason: "aborted" };
    const reason = error instanceof Error ? error.message : "unknown_error";
    defaultLogger("failed", reason);
    return { status: "failed", reason };
  }
}

export async function loadArtConstellationRelease(
  baseUrl: string,
  fetcher: typeof fetch = fetch,
  signal?: AbortSignal,
): Promise<ArtConstellationLoadResult> {
  try {
    const base = assertSameOrigin(baseUrl);
    const manifestResult = await loadStaticRelease(
      new URL("manifest.json", base).href,
      fetcher,
      defaultLogger,
      signal,
    );
    if (manifestResult.status !== "loaded") {
      return {
        status: manifestResult.status === "empty" ? "failed" : manifestResult.status,
        reason: `manifest_${manifestResult.status}`,
      };
    }
    const { manifest } = manifestResult;
    if (manifest.id !== expectedReleaseIdFromBase(base)) {
      throw new Error("manifest_release_identity_mismatch");
    }
    const artifactFiles = new Map(manifest.manifest_files.map((file) => [file.path, file]));
    for (const name of ART_CONSTELLATION_DECLARED_ARTIFACTS) {
      if (!artifactFiles.has(name)) throw new Error(`manifest_missing_${name}`);
    }
    if (manifest.id.startsWith("release:art-expansion-") && !artifactFiles.has(ASSET_RESOLUTION_ARTIFACT)) {
      throw new Error(`manifest_missing_${ASSET_RESOLUTION_ARTIFACT}`);
    }
    const artifacts = await Promise.all(
      ART_CONSTELLATION_INITIAL_ARTIFACTS.map(async (name) => {
        const file = artifactFiles.get(name);
        if (!file) throw new Error(`manifest_missing_${name}`);
        return [name, await fetchVerifiedJson(new URL(name, base).href, file.sha256, fetcher, signal)] as const;
      }),
    );
    const data = Object.fromEntries(artifacts) as Record<(typeof ART_CONSTELLATION_INITIAL_ARTIFACTS)[number], unknown>;
    const graphRoot = requiredRecord(data["graph-summary.json"], "graph_summary_root");
    const coreReleaseId = requiredString(graphRoot.release_id, "graph_release_id");
    const { summary, artifactPaths } = parseGraphSummary(data["graph-summary.json"], coreReleaseId);
    const expectedArtifactPaths: Record<string, string> = {
      artists: "artists.json", contexts: "contexts.json", relationships: "relationships.json",
      artworks: "artworks.json", evidence: "evidence.json", sources: "sources.json",
      search_index: "search-index.json", layout: "layout.json", facets: "facets.json", rights: "rights.json",
      media_index: "media-index.json", withdrawal: "withdrawal-mapping.json",
    };
    if (Object.entries(expectedArtifactPaths).some(([key, path]) => artifactPaths[key] !== path)) {
      throw new Error("graph_artifact_paths_invalid");
    }

    const artists = parseArtists(data["artists.json"], coreReleaseId);
    const explorerReference = artifactFiles.get("relationship-explorer-config.json");
    if (new Set([
      "release:art-expansion-batch-01-1.5.1",
      "release:art-expansion-batch-02-1.6.0",
    ]).has(coreReleaseId) && !explorerReference) {
      throw new Error("manifest_missing_relationship-explorer-config.json");
    }
    const explorerRaw = explorerReference
      ? await fetchVerifiedJson(new URL(explorerReference.path, base).href, explorerReference.sha256, fetcher, signal)
      : null;
    const release: ArtConstellationRelease = {
      manifestId: manifest.id,
      version: manifest.version,
      isPublicRelease: manifest.public_release,
      summary,
      artists,
      searchEntries: parseSearchEntries(data["search-index.json"], coreReleaseId, artists),
      layout: parseLayout(data["layout.json"], coreReleaseId),
      explorerConfig: parseExplorerConfig(explorerRaw, coreReleaseId, artists),
      facets: parseFacets(data["facets.json"], coreReleaseId),
    };
    assertInitialClosure(release);

    const artifact = async (name: (typeof ART_CONSTELLATION_DECLARED_ARTIFACTS)[number], detailSignal?: AbortSignal) => {
      const file = artifactFiles.get(name);
      if (!file) throw new Error(`manifest_missing_${name}`);
      const value = await fetchVerifiedJson(new URL(name, base).href, file.sha256, fetcher, detailSignal);
      return value;
    };

    let relationshipIndexCache: RelationshipIndex | null = null;
    let sourcesCache: SourceRecord[] | null = null;
    let artworkMediaCache: { artworks: ArtworkRecord[]; media: MediaAsset[] } | null = null;
    let claimsCache: ClaimRecord[] | null = null;
    let evidenceCache: EvidenceRecord[] | null = null;
    const loadRelationshipIndex = async (detailSignal?: AbortSignal): Promise<DetailLoadResult<RelationshipIndex>> =>
      detailResult(async () => {
        if (relationshipIndexCache) return relationshipIndexCache;
        const [contextsRaw, relationshipsRaw] = await Promise.all([
          artifact("contexts.json", detailSignal),
          artifact("relationships.json", detailSignal),
        ]);
        const index = {
          contexts: parseContexts(contextsRaw, coreReleaseId),
          relationships: parseRelationships(relationshipsRaw, coreReleaseId),
        };
        assertRelationshipIndexClosure(release, index);
        relationshipIndexCache = index;
        return index;
      }, detailSignal);

    const loadSourcesArtifact = async (detailSignal?: AbortSignal) => {
      if (sourcesCache) return sourcesCache;
      const sources = parseSources(await artifact("sources.json", detailSignal), coreReleaseId);
      sourcesCache = sources;
      return sources;
    };

    const loadArtworkMediaArtifacts = async (detailSignal?: AbortSignal) => {
      if (artworkMediaCache) return artworkMediaCache;
      const [artworksRaw, mediaRaw, attributionsRaw, withdrawalRaw, assetResolution] = await Promise.all([
        artifact("artworks.json", detailSignal),
        artifact("media-index.json", detailSignal),
        fetchVerifiedJson(
          new URL(manifest.attribution_manifest.path, base).href,
          manifest.attribution_manifest.sha256,
          fetcher,
          detailSignal,
        ),
        artifact("withdrawal-mapping.json", detailSignal),
        artifactFiles.has(ASSET_RESOLUTION_ARTIFACT)
          ? loadAssetResolutionManifest(base, manifest, fetcher, detailSignal)
          : Promise.resolve(null),
      ]);
      const runtimeAssetFiles = new Map<string, RuntimeAssetFile>([
        ...manifest.manifest_files,
        ...(manifest.referenced_files ?? []),
        ...(manifest.materialized_asset_files ?? []),
        ...(assetResolution?.referenced_files ?? []),
        ...(assetResolution?.materialized_asset_files ?? []),
      ].map((file) => [file.path, file]));
      const artworks = parseArtworks(artworksRaw, coreReleaseId);
      const media = parseMediaSupport(
        mediaRaw,
        attributionsRaw,
        withdrawalRaw,
        coreReleaseId,
        base,
        artworks,
        manifest,
        runtimeAssetFiles,
      );
      assertArtistArtworkClosure(release, artworks, media);
      artworkMediaCache = { artworks, media };
      return artworkMediaCache;
    };

    const loadClaimsArtifact = async (detailSignal?: AbortSignal) => {
      if (claimsCache) return claimsCache;
      claimsCache = parseClaims(await artifact("claims.json", detailSignal), coreReleaseId);
      return claimsCache;
    };

    const loadEvidenceArtifact = async (detailSignal?: AbortSignal) => {
      if (evidenceCache) return evidenceCache;
      evidenceCache = parseEvidence(await artifact("evidence.json", detailSignal), coreReleaseId);
      return evidenceCache;
    };

    const dataSource: ArtConstellationDataSource = {
      loadRelationshipIndex,
      loadArtworkCatalog: (detailSignal) => detailResult<ArtworkCatalog>(
        () => loadArtworkMediaArtifacts(detailSignal),
        detailSignal,
      ),
      loadArtworkDetails: (artworkId, detailSignal) => detailResult<ArtworkDetails>(async () => {
        const [artworkMedia, claims, evidence, sources] = await Promise.all([
          loadArtworkMediaArtifacts(detailSignal),
          loadClaimsArtifact(detailSignal),
          loadEvidenceArtifact(detailSignal),
          loadSourcesArtifact(detailSignal),
        ]);
        const artwork = artworkMedia.artworks.find((candidate) => candidate.id === artworkId);
        if (!artwork) throw new Error("unknown_artwork_id");
        const artist = release.artists.find((candidate) => candidate.id === artwork.artistId);
        if (!artist || !artist.artworkIds.includes(artwork.id)) throw new Error("artwork_artist_reference_closure");
        const selectedClaims = claims.filter((claim) => claim.subjectId === artwork.id);
        if (selectedClaims.length === 0) throw new Error("artwork_claim_closure");
        const evidenceIds = new Set(selectedClaims.flatMap((claim) => claim.evidenceIds));
        const selectedEvidence = evidence.filter((item) => evidenceIds.has(item.id));
        if (
          selectedEvidence.length !== evidenceIds.size ||
          selectedClaims.some((claim) => claim.evidenceIds.some((id) => !selectedEvidence.some((item) => item.id === id))) ||
          selectedEvidence.some((item) => !item.claimIds.some((id) => selectedClaims.some((claim) => claim.id === id)))
        ) throw new Error("artwork_evidence_reference_closure");
        const sourceIds = new Set([
          ...artwork.sourceIds,
          ...selectedEvidence.flatMap((item) => item.sourceIds),
        ]);
        const selectedSources = sources.filter((source) => sourceIds.has(source.id));
        if (selectedSources.length !== sourceIds.size) throw new Error("artwork_source_reference_closure");
        return {
          artwork,
          artist,
          media: artworkMedia.media.filter((asset) => asset.artworkId === artwork.id),
          claims: selectedClaims,
          evidence: selectedEvidence,
          sources: selectedSources,
        };
      }, detailSignal),
      loadArtistSources: (artistId, detailSignal) => detailResult<ArtistSources>(async () => {
        const artist = release.artists.find((candidate) => candidate.id === artistId);
        if (!artist) throw new Error("unknown_artist_id");
        const [sources, artworkMedia] = await Promise.all([
          loadSourcesArtifact(detailSignal),
          loadArtworkMediaArtifacts(detailSignal),
        ]);
        const sourceIds = new Set(sources.map((source) => source.id));
        const artworks = artworkMedia.artworks.filter((artwork) => artist.artworkIds.includes(artwork.id));
        const relevantSourceIds = new Set([...artist.sourceIds, ...artworks.flatMap((artwork) => artwork.sourceIds)]);
        if ([...relevantSourceIds].some((id) => !sourceIds.has(id))) throw new Error("artist_source_reference_closure");
        return {
          artist,
          artworks,
          media: artworkMedia.media.filter((asset) => artist.artworkIds.includes(asset.artworkId)),
          sources: sources.filter((source) => relevantSourceIds.has(source.id)),
        };
      }, detailSignal),
      loadRelationshipDetails: (relationshipId, detailSignal) => detailResult<RelationshipDetails>(async () => {
        const indexResult = await loadRelationshipIndex(detailSignal);
        if (indexResult.status !== "loaded") throw new Error(indexResult.reason);
        const relationship = indexResult.data.relationships.find((candidate) => candidate.id === relationshipId);
        if (!relationship) throw new Error("unknown_relationship_id");
        const [artworkMedia, evidenceRaw, sources] = await Promise.all([
          loadArtworkMediaArtifacts(detailSignal),
          loadEvidenceArtifact(detailSignal),
          loadSourcesArtifact(detailSignal),
        ]);
        const evidence = evidenceRaw;
        assertDetailClosure(relationship, artworkMedia.artworks, evidence, sources);
        const selectedArtworks = artworkMedia.artworks.filter((artwork) => relationship.supportingArtworkIds.includes(artwork.id));
        const selectedEvidence = evidence.filter((item) => relationship.evidenceIds.includes(item.id));
        const detailSourceIds = new Set([
          ...relationship.sourceIds,
          ...selectedArtworks.flatMap((artwork) => artwork.sourceIds),
          ...selectedEvidence.flatMap((item) => item.sourceIds),
        ]);
        return {
          relationship,
          contexts: indexResult.data.contexts.filter((context) => relationship.contextIds.includes(context.id)),
          artworks: selectedArtworks,
          media: artworkMedia.media.filter((asset) => relationship.supportingArtworkIds.includes(asset.artworkId)),
          evidence: selectedEvidence,
          sources: sources.filter((source) => detailSourceIds.has(source.id)),
        };
      }, detailSignal),
      loadRights: (detailSignal) => detailResult<RightsDetails>(async () => {
        const rights = parseRights(await artifact("rights.json", detailSignal), coreReleaseId, base);
        if (
          rights.mediaCount !== release.summary.mediaCount ||
          rights.mediaBytes !== release.summary.mediaBytes ||
          rights.approvedMediaArtworks !== release.summary.approvedMediaArtworkCount ||
          rights.noImageArtworks !== release.summary.noImageArtworkCount
        ) throw new Error("rights_summary_count_mismatch");
        const noticesReference = manifest.third_party_notices_manifest;
        if (
          rights.noticesPath !== noticesReference.path ||
          rights.attributionsPath !== manifest.attribution_manifest.path ||
          rights.withdrawalPath !== "withdrawal-mapping.json"
        ) throw new Error("rights_support_path_mismatch");
        const [noticesRaw, sourceRegistryRaw, licenseDecisionsRaw, attributionsRaw] = await Promise.all([
          fetchVerifiedJson(new URL(noticesReference.path, base).href, noticesReference.sha256, fetcher, detailSignal),
          fetchVerifiedJson(
            new URL(manifest.source_registry_manifest.path, base).href,
            manifest.source_registry_manifest.sha256,
            fetcher,
            detailSignal,
          ),
          fetchVerifiedJson(
            new URL(manifest.license_decisions.registry_path, base).href,
            manifest.license_decisions.registry_sha256,
            fetcher,
            detailSignal,
          ),
          fetchVerifiedJson(
            new URL(manifest.attribution_manifest.path, base).href,
            manifest.attribution_manifest.sha256,
            fetcher,
            detailSignal,
          ),
        ]);
        assertRightsSupportArtifacts(sourceRegistryRaw, licenseDecisionsRaw, attributionsRaw, manifest);
        return { rights, notices: parseNotices(noticesRaw) };
      }, detailSignal),
    };
    return { status: "loaded", release, dataSource };
  } catch (error) {
    if (signal?.aborted) return { status: "failed", reason: "aborted" };
    const reason = error instanceof Error ? error.message : "unknown_error";
    defaultLogger("failed", reason);
    return { status: "failed", reason };
  }
}
