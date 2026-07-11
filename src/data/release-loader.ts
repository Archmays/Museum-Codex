export const SUPPORTED_RELEASE_SCHEMA_MAJOR = 1;

type ArtifactReference = { path: string; sha256: string };
type ManifestFile = ArtifactReference & {
  bytes: number;
  record_type: string;
  schema_path: string | null;
  record_ids: string[];
};

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
  status: "publishable" | "published";
  predecessor: string | null;
  public_release: true;
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
};

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

function isCanonicalPublicRelease(value: unknown): value is ReleaseManifest {
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
  const lifecycleIsPublic =
    (value.status === "publishable" || value.status === "published") &&
    value.public_release === true &&
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
    sameSet(recordIdsFor(files, "media"), includedMediaIds) &&
    sameSet(recordIdsFor(files, "third_party_notices"), [...includedSourceIds, ...includedMediaIds]) &&
    sameSet(recordIdsFor(files, "attributions"), includedMediaIds) &&
    sameSet(recordIdsFor(files, "license_decisions"), licenseDecisionIds);

  return identityIsValid && lifecycleIsPublic && buildMetadataIsValid && closureIsPresent;
}

function defaultLogger(event: "missing" | "incompatible" | "failed", detail?: string) {
  if (import.meta.env.DEV) console.info(`[museum-release] ${event}`, detail ?? "");
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
): Promise<ReleaseLoadResult> {
  try {
    const response = await fetcher(manifestUrl, { headers: { Accept: "application/json" } });
    if (response.status === 404) {
      logger("missing");
      return { status: "missing" };
    }
    if (!response.ok) {
      logger("failed", `http_${response.status}`);
      return { status: "failed" };
    }

    const data: unknown = await response.json();
    if (!isRecord(data) || typeof data.schema_version !== "string") {
      logger("failed", "invalid_manifest_shape");
      return { status: "failed" };
    }
    const major = Number.parseInt(data.schema_version.split(".")[0] ?? "", 10);
    if (major !== SUPPORTED_RELEASE_SCHEMA_MAJOR) {
      logger("incompatible", data.schema_version);
      return { status: "incompatible", foundVersion: data.schema_version };
    }
    if (!isCanonicalPublicRelease(data)) {
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
