import type {
  ArtConstellationDataSource,
  ArtConstellationRelease,
  ArtistRecord,
  ArtistSources,
  ArtworkMediaDecision,
  ArtworkRecord,
  ContextRecord,
  DetailLoadResult,
  EvidenceRecord,
  GraphSummary,
  LayoutNode,
  LocalizedText,
  MediaAsset,
  RelationshipDetails,
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
    files.filter((file) => file.record_type === "media").every((file) => file.record_ids.length > 0) &&
    recordIdsFor(files, "media").every((id) => includedMediaIds.includes(id)) &&
    new Set(recordIdsFor(files, "media")).size === recordIdsFor(files, "media").length &&
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
const ART_CONSTELLATION_RELEASE_ID = "release:art-constellation-1.0.0";
const ART_CONSTELLATION_MEDIA_BUNDLE_HASH = "sha256:3aa84fa7df37c4823cd2cb1f92c7e1843e7dea70b7cfd683528b25698951d565";
const ART_CONSTELLATION_INITIAL_ARTIFACTS = [
  "graph-summary.json",
  "artists.json",
  "search-index.json",
  "layout.json",
  "facets.json",
] as const;
const ART_CONSTELLATION_DECLARED_ARTIFACTS = [
  ...ART_CONSTELLATION_INITIAL_ARTIFACTS,
  "contexts.json",
  "relationships.json",
  "artworks.json",
  "evidence.json",
  "sources.json",
  "rights.json",
  "media-index.json",
  "withdrawal-mapping.json",
] as const;
const RELATIONSHIP_TYPES = ["shared_subject", "shared_material", "shared_technique"] as const;
const MEDIA_DECISIONS = [
  "approved_self_hosted",
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
    return code <= 31 || code === 127;
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

function artworkObjectUrl(value: unknown, artworkId: string, sourceIds: string[]) {
  const rawUrl = optionalString(value);
  if (!rawUrl) return null;
  const url = httpsUrl(rawUrl, "artwork_official_object_url");
  const aicId = /^artwork:aic-(\d+)$/.exec(artworkId)?.[1];
  const metId = /^artwork:met-(\d+)$/.exec(artworkId)?.[1];
  const matchesAic = Boolean(
    aicId && sourceIds.includes("source:aic_api") && url.origin === "https://api.artic.edu" &&
    url.pathname === `/api/v1/artworks/${aicId}` && !url.search && !url.hash,
  );
  const matchesMet = Boolean(
    metId && sourceIds.includes("source:met_open_access") && url.origin === "https://www.metmuseum.org" &&
    url.pathname === `/art/collection/search/${metId}` && !url.search && !url.hash,
  );
  if (!matchesAic && !matchesMet) throw new Error("artwork_official_object_source_mismatch");
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
  return objectList(value, label).map((item) => localized(item.labels ?? item.label, `${label}_labels`));
}

function parseArtists(raw: unknown, releaseId: string): ArtistRecord[] {
  return assertEnvelope(requiredRecord(raw, "artists_root"), releaseId, "artists").map((artist) => {
    const places = objectList(artist.activity_places, "artist_activity_places");
    const periods = stringList(artist.historical_periods, "artist_periods");
    const traditions = stringList(artist.artistic_traditions, "artist_traditions");
    const lifeDates = requiredRecord(artist.life_dates, "artist_life_dates");
    const birth = requiredRecord(lifeDates.birth, "artist_birth");
    const death = requiredRecord(lifeDates.death, "artist_death");
    const review = requiredRecord(artist.review, "artist_review");
    const birthDisplay = requiredString(birth.display_value, "artist_birth_display");
    const deathDisplay = requiredString(death.display_value, "artist_death_display");
    return {
      id: requiredString(artist.id, "artist_id"),
      labels: localized(artist.labels, "artist_labels"),
      summary: localized(artist.summary, "artist_summary"),
      aliases: aliasTexts(artist.aliases),
      period: requiredString(periods[0], "artist_period"),
      region: requiredString(places[0]?.label, "artist_region"),
      tradition: traditions[0] ?? null,
      lifeDisplay: { "zh-Hans": `${birthDisplay}—${deathDisplay}`, en: `${birthDisplay}–${deathDisplay}` },
      mediaPractice: localized(artist.media_practice, "artist_media_practice"),
      claimIds: stringList(artist.verified_claim_ids, "artist_claim_ids"),
      sourceIds: stringList(artist.source_ids, "artist_source_ids"),
      relationCount: requiredNumber(artist.relation_count, "artist_relation_count"),
      artworkIds: stringList(artist.artwork_ids, "artist_artwork_ids"),
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
      shortExplanation: localized(relationship.short_explanation, "relationship_short_explanation"),
      whatItMeans: localized(relationship.what_it_means, "relationship_what_it_means"),
      doesNotMean: localized(relationship.what_it_does_not_mean, "relationship_does_not_mean"),
      contextIds: stringList(relationship.context_ids, "relationship_context_ids"),
      supportingArtworkIds: stringList(relationship.supporting_artwork_ids, "relationship_artwork_ids"),
      evidenceConfidence: requiredNumber(relationship.evidence_confidence, "relationship_confidence"),
      curatorialRelevance: requiredNumber(relationship.curatorial_relevance, "relationship_relevance"),
      claimIds: stringList(relationship.claim_ids, "relationship_claim_ids"),
      evidenceIds: stringList(relationship.evidence_ids, "relationship_evidence_ids"),
      sourceIds: stringList(relationship.source_ids, "relationship_source_ids"),
      limitations: optionalLocalized(relationship.limitations, "relationship_limitations"),
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
      artistId: requiredString(artwork.artist_id, "artwork_artist_id"),
      title: localized(artwork.labels, "artwork_title"),
      dateDisplay: optionalLocalized(creation.description, "artwork_creation_description"),
      mediumDisplay: mediumItems.length === 0 ? null : {
        "zh-Hans": mediumItems.map((item) => item["zh-Hans"]).join("、"),
        en: mediumItems.map((item) => item.en).join(", "),
      },
      institution: localized(institution.label, "artwork_institution_label"),
      objectUrl: artworkObjectUrl(artwork.official_object_url, id, sourceIds),
      sourceIds,
      attribution: null,
      accessionNumber: optionalString(artwork.accession_number),
      materials,
      techniques,
      subjects: localizedItems(artwork.subjects, "artwork_subjects"),
      metadataLicense: requiredString(metadataLicense.rule_id, "artwork_metadata_license_rule"),
      limitations: optionalLocalized(artwork.limitations, "artwork_limitations"),
      media: {
        decision,
        reasonCodes: stringList(media.reason_codes, "artwork_media_reason_codes"),
        representativeMediaId,
        mediaIds,
      },
    };
  });
}

function parseEvidence(raw: unknown, releaseId: string): EvidenceRecord[] {
  return assertEnvelope(requiredRecord(raw, "evidence_root"), releaseId, "evidence").map((evidence) => {
    const locator = requiredRecord(evidence.locator, "evidence_locator");
    return {
      id: requiredString(evidence.id, "evidence_id"),
      sourceIds: stringList(evidence.source_ids, "evidence_source_ids"),
      summary: localized(evidence.summary, "evidence_summary"),
      locator: [optionalString(locator.record_id), optionalString(locator.section)].filter(Boolean).join(" · ") || null,
      reliabilityNote: localized(evidence.reliability_note, "evidence_reliability_note"),
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
  if (
    root.schema_version !== ART_CONSTELLATION_SCHEMA_VERSION || root.release_id !== releaseId ||
    root.algorithm !== "deterministic_circle_v1" || root.seed !== "museum-04-art-constellation-1.0.0"
  ) throw new Error("layout_contract");
  return objectList(root.nodes, "layout_nodes").map((node) => ({
    artistId: requiredString(node.artist_id, "layout_artist_id"),
    x: requiredNumber(node.x, "layout_x"),
    y: requiredNumber(node.y, "layout_y"),
  }));
}

function facetValues(value: unknown, label: string) {
  return objectList(value, label).map((item) => requiredString(item.value, `${label}_value`));
}

function parseFacets(raw: unknown, releaseId: string) {
  const root = requiredRecord(raw, "facets_root");
  if (root.schema_version !== ART_CONSTELLATION_SCHEMA_VERSION || root.release_id !== releaseId) {
    throw new Error("facets_envelope");
  }
  const facets = requiredRecord(root.facets, "facets");
  const relationshipTypes = facetValues(facets.relationship_types, "relationship_type_facets") as RelationshipType[];
  if (relationshipTypes.some((type) => !RELATIONSHIP_TYPES.includes(type))) throw new Error("facet_relationship_type");
  return {
    periods: facetValues(facets.periods, "period_facets"),
    regions: facetValues(facets.regions, "region_facets"),
    traditions: facetValues(facets.traditions, "tradition_facets"),
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
  if (
    code.identifier !== "ALL-RIGHTS-RESERVED" || code.status !== "decided" ||
    content.identifier !== "ALL-RIGHTS-RESERVED" || content.status !== "decided" ||
    media.count !== 242 || media.bytes !== 35_907_176 || media.approved_artworks !== 31 ||
    media.no_image_artworks !== 13 || media.external_runtime_count !== 0 || media.blocked_asset_count !== 0 ||
    media.media_bundle_hash !== ART_CONSTELLATION_MEDIA_BUNDLE_HASH
  ) throw new Error("rights_profile_invalid");
  return {
    codeRights: localized(code.statement, "code_rights_statement"),
    originalContentRights: localized(content.statement, "content_rights_statement"),
    thirdPartyMetadata: [localized(metadata.statement, "metadata_rights_statement")],
    mediaStatement: localized(media.statement, "media_rights_statement"),
    mediaCount: 242,
    mediaBytes: 35_907_176,
    approvedMediaArtworks: 31,
    noImageArtworks: 13,
    mediaBundleId: requiredString(media.media_bundle_id, "media_bundle_id"),
    mediaBundleHash: requiredString(media.media_bundle_hash, "media_bundle_hash"),
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
  if (
    counts.artists !== 12 || counts.contexts !== 31 || counts.relationships !== 36 ||
    counts.artworks !== 44 || counts.media !== 242 || counts.media_bytes !== 35_907_176 ||
    counts.approved_media_artworks !== 31 || counts.no_image_artworks !== 13 ||
    counts.media_provenance_parents !== 31 || levels.A !== 0 || levels.B !== 0 || levels.C !== 36 ||
    semantics.algorithmic !== false || semantics.causal !== false || semantics.directed !== false ||
    initialState.view !== "graph" || initialState.edges_visible !== false || initialState.focused_artist_id !== null
  ) throw new Error("graph_summary_profile_invalid");
  const relationshipTypeCounts = {
    shared_subject: requiredNumber(relationTypes.shared_subject, "shared_subject_count"),
    shared_material: requiredNumber(relationTypes.shared_material, "shared_material_count"),
    shared_technique: requiredNumber(relationTypes.shared_technique, "shared_technique_count"),
  };
  const summary: GraphSummary = {
    releaseId,
    title: localized(root.title, "graph_title"),
    artistCount: 12,
    contextCount: 31,
    relationshipCount: 36,
    artworkCount: requiredNumber(counts.artworks, "artwork_count"),
    mediaCount: 242,
    mediaBytes: 35_907_176,
    approvedMediaArtworkCount: 31,
    noImageArtworkCount: 13,
    levelCounts: { A: 0, B: 0, C: 36 },
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
  if (!SAFE_PATH.test(path) || !/^assets\/[a-z0-9._-]+\/[0-9]+w\.(?:jpg|webp)$/i.test(path)) {
    throw new Error("media_src_not_release_child");
  }
  const url = new URL(path, base);
  const basePath = base.pathname.endsWith("/") ? base.pathname : `${base.pathname}/`;
  if (url.origin !== base.origin || !url.pathname.startsWith(`${basePath}assets/`)) {
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
  artifactFiles: Map<string, ManifestFile>,
): MediaAsset[] {
  const root = requiredRecord(mediaRaw, "media_index_root");
  if (
    root.schema_version !== ART_CONSTELLATION_SCHEMA_VERSION || root.release_id !== releaseId ||
    root.media_bundle_hash !== ART_CONSTELLATION_MEDIA_BUNDLE_HASH
  ) throw new Error("media_index_envelope");
  const delivery = requiredRecord(root.delivery_policy, "media_delivery_policy");
  const counts = requiredRecord(root.counts, "media_counts");
  if (
    delivery.external_runtime_api !== false || delivery.external_delivery_count !== 0 ||
    delivery.blocked_asset_count !== 0 || delivery.preferred !== "self_hosted" ||
    delivery.low_bandwidth_default !== "metadata_only" || counts.approved_artworks !== 31 ||
    counts.no_image_artworks !== 13 || counts.assets !== 242 || counts.bytes !== 35_907_176
  ) throw new Error("media_delivery_profile_invalid");

  const artworkById = new Map(artworks.map((artwork) => [artwork.id, artwork]));
  const mediaArtworkRecords = objectList(root.artworks, "media_index_artworks");
  if (mediaArtworkRecords.length !== 44 || artworkById.size !== 44) throw new Error("media_artwork_count");
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
    assets.length !== 242 || new Set(assetIds).size !== 242 ||
    assets.reduce((sum, asset) => sum + asset.bytes, 0) !== 35_907_176 ||
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
    rawAttributions.length !== 273 || new Set(rawAttributionIds).size !== 273 ||
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
    if (
      !attribution || !withdrawal || withdrawal.artworkId !== asset.artworkId ||
      !withdrawal.paths.includes(asset.publicPath)
    ) throw new Error("media_rights_reference_closure");
    return {
      ...asset,
      ...attribution,
      withdrawalStatus: "active" as const,
      withdrawalNotice: withdrawal.notice,
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

function assertSameOrigin(baseUrl: string) {
  const documentUrl = typeof window === "undefined" ? "https://museum-codex.invalid/" : window.location.href;
  const base = new URL(baseUrl, documentUrl);
  if (typeof window !== "undefined" && base.origin !== window.location.origin) throw new Error("release_cross_origin");
  return base;
}

function assertInitialClosure(release: ArtConstellationRelease) {
  const artistIds = new Set(release.artists.map((artist) => artist.id));
  if (
    artistIds.size !== 12 || release.layout.length !== 12 || release.searchEntries.length !== 12
  ) throw new Error("release_counts_invalid");
  if (new Set(release.layout.map((node) => node.artistId)).size !== 12 || release.layout.some((node) => !artistIds.has(node.artistId))) {
    throw new Error("layout_artist_closure");
  }
  if (
    new Set(release.searchEntries.map((entry) => entry.id)).size !== 12 ||
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
  if (artworks.length !== 44 || artworkIds.size !== 44 || artworks.some((artwork) => !artistIds.has(artwork.artistId))) {
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
  for (const relationship of index.relationships) {
    if (
      !artistIds.has(relationship.sourceArtistId) || !artistIds.has(relationship.targetArtistId) ||
      relationship.sourceArtistId === relationship.targetArtistId ||
      relationship.contextIds.some((id) => !contextIds.has(id))
    ) throw new Error("relationship_reference_closure");
    seenTypes[relationship.type] += 1;
    connectedArtists.add(relationship.sourceArtistId);
    connectedArtists.add(relationship.targetArtistId);
  }
  if (
    connectedArtists.size !== release.artists.length ||
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
    if (
      manifest.id !== ART_CONSTELLATION_RELEASE_ID || manifest.version !== "1.0.0" ||
      manifest.public_release !== true || manifest.status !== "publishable" ||
      manifest.included_media_asset_ids.length !== 273 || manifest.attribution_manifest.asset_ids.length !== 273 ||
      manifest.withdrawals.length !== 0 || manifest.deprecations.length !== 0
    ) return { status: "failed", reason: "manifest_profile_invalid" };

    const artifactFiles = new Map(manifest.manifest_files.map((file) => [file.path, file]));
    for (const name of ART_CONSTELLATION_DECLARED_ARTIFACTS) {
      if (!artifactFiles.has(name)) throw new Error(`manifest_missing_${name}`);
    }
    const artifacts = await Promise.all(
      ART_CONSTELLATION_INITIAL_ARTIFACTS.map(async (name) => {
        const file = artifactFiles.get(name);
        if (!file) throw new Error(`manifest_missing_${name}`);
        return [name, await fetchVerifiedJson(new URL(name, base).href, file.sha256, fetcher, signal)] as const;
      }),
    );
    const data = Object.fromEntries(artifacts) as Record<(typeof ART_CONSTELLATION_INITIAL_ARTIFACTS)[number], unknown>;
    const { summary, artifactPaths } = parseGraphSummary(data["graph-summary.json"], manifest.id);
    const expectedArtifactPaths: Record<string, string> = {
      artists: "artists.json", contexts: "contexts.json", relationships: "relationships.json",
      artworks: "artworks.json", evidence: "evidence.json", sources: "sources.json",
      search_index: "search-index.json", layout: "layout.json", facets: "facets.json", rights: "rights.json",
      media_index: "media-index.json", withdrawal: "withdrawal-mapping.json",
    };
    if (Object.entries(expectedArtifactPaths).some(([key, path]) => artifactPaths[key] !== path)) {
      throw new Error("graph_artifact_paths_invalid");
    }

    const artists = parseArtists(data["artists.json"], manifest.id);
    const release: ArtConstellationRelease = {
      manifestId: manifest.id,
      version: manifest.version,
      isPublicRelease: manifest.public_release,
      summary,
      artists,
      searchEntries: parseSearchEntries(data["search-index.json"], manifest.id, artists),
      layout: parseLayout(data["layout.json"], manifest.id),
      facets: parseFacets(data["facets.json"], manifest.id),
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
    const loadRelationshipIndex = async (detailSignal?: AbortSignal): Promise<DetailLoadResult<RelationshipIndex>> =>
      detailResult(async () => {
        if (relationshipIndexCache) return relationshipIndexCache;
        const [contextsRaw, relationshipsRaw] = await Promise.all([
          artifact("contexts.json", detailSignal),
          artifact("relationships.json", detailSignal),
        ]);
        const index = {
          contexts: parseContexts(contextsRaw, manifest.id),
          relationships: parseRelationships(relationshipsRaw, manifest.id),
        };
        assertRelationshipIndexClosure(release, index);
        relationshipIndexCache = index;
        return index;
      }, detailSignal);

    const loadSourcesArtifact = async (detailSignal?: AbortSignal) => {
      if (sourcesCache) return sourcesCache;
      const sources = parseSources(await artifact("sources.json", detailSignal), manifest.id);
      sourcesCache = sources;
      return sources;
    };

    const loadArtworkMediaArtifacts = async (detailSignal?: AbortSignal) => {
      if (artworkMediaCache) return artworkMediaCache;
      const [artworksRaw, mediaRaw, attributionsRaw, withdrawalRaw] = await Promise.all([
        artifact("artworks.json", detailSignal),
        artifact("media-index.json", detailSignal),
        fetchVerifiedJson(
          new URL(manifest.attribution_manifest.path, base).href,
          manifest.attribution_manifest.sha256,
          fetcher,
          detailSignal,
        ),
        artifact("withdrawal-mapping.json", detailSignal),
      ]);
      const artworks = parseArtworks(artworksRaw, manifest.id);
      const media = parseMediaSupport(
        mediaRaw,
        attributionsRaw,
        withdrawalRaw,
        manifest.id,
        base,
        artworks,
        manifest,
        artifactFiles,
      );
      assertArtistArtworkClosure(release, artworks, media);
      artworkMediaCache = { artworks, media };
      return artworkMediaCache;
    };

    const dataSource: ArtConstellationDataSource = {
      loadRelationshipIndex,
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
          artifact("evidence.json", detailSignal),
          loadSourcesArtifact(detailSignal),
        ]);
        const evidence = parseEvidence(evidenceRaw, manifest.id);
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
        const rights = parseRights(await artifact("rights.json", detailSignal), manifest.id, base);
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
