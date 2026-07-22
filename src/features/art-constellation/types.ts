import type { Locale } from "../../i18n/translations";

export type LocalizedText = {
  "zh-Hans": string;
  en: string;
};

export type ViewMode = "graph" | "list" | "table";
export type RelationshipType = "shared_material" | "shared_subject" | "shared_technique";

export type ArtistRecord = {
  id: string;
  publicSlug: string;
  profileKind: "gallery" | "collection";
  sourceLanguageName: string | null;
  transliterations: string[];
  gallerySequence: string[];
  labels: LocalizedText;
  summary: LocalizedText;
  aliases: string[];
  period: string;
  region: string;
  tradition: string | null;
  lifeDisplay: LocalizedText | null;
  mediaPractice: LocalizedText;
  claimIds: string[];
  sourceIds: string[];
  relationCount: number;
  artworkIds: string[];
  representativeMediaId: string | null;
  approvedMediaArtworkCount: number;
  reviewer: string;
  reviewDate: string;
};

export type ContextRecord = {
  id: string;
  type: string;
  labels: LocalizedText;
};

export type RelationshipRecord = {
  id: string;
  sourceArtistId: string;
  targetArtistId: string;
  type: RelationshipType;
  level: "C";
  title: LocalizedText;
  shortExplanation: LocalizedText;
  whatItMeans: LocalizedText;
  doesNotMean: LocalizedText;
  contextIds: string[];
  supportingArtworkIds: string[];
  evidenceConfidence: number;
  curatorialRelevance: number;
  claimIds: string[];
  evidenceIds: string[];
  sourceIds: string[];
  limitations: LocalizedText | null;
  reviewer: string;
  reviewDate: string;
};

export type ArtworkRecord = {
  id: string;
  publicSlug: string;
  artistId: string;
  title: LocalizedText;
  dateDisplay: LocalizedText | null;
  mediumDisplay: LocalizedText | null;
  institution: LocalizedText | null;
  objectUrl: string | null;
  sourceIds: string[];
  attribution: string | null;
  accessionNumber: string | null;
  materials: LocalizedText[];
  techniques: LocalizedText[];
  subjects: LocalizedText[];
  metadataLicense: string;
  limitations: LocalizedText | null;
  media: ArtworkMediaState;
};

export type ArtworkMediaDecision =
  | "approved_self_hosted"
  | "external_link_only"
  | "metadata_only"
  | "metadata_only_after_automated_review"
  | "blocked_source_unavailable"
  | "blocked_rights_conflict";

export type ArtworkMediaState = {
  decision: ArtworkMediaDecision;
  reasonCodes: string[];
  representativeMediaId: string | null;
  mediaIds: string[];
};

export type MediaAsset = {
  id: string;
  artworkId: string;
  parentMediaId: string;
  src: string;
  publicPath: string;
  format: "jpeg" | "webp";
  mimeType: "image/jpeg" | "image/webp";
  width: number;
  height: number;
  bytes: number;
  sha256: string;
  role: "thumbnail" | "detail" | "zoom";
  attribution: string;
  changesStatement: string;
  licenseIdentifier: string;
  licenseUrl: string;
  sourceUrl: string;
  withdrawalStatus: "active";
  withdrawalNotice: string;
};

export type EvidenceRecord = {
  id: string;
  claimIds: string[];
  sourceIds: string[];
  summary: LocalizedText;
  locator: string | null;
  reliabilityNote: LocalizedText;
};

export type ClaimRecord = {
  id: string;
  subjectId: string;
  predicate: string;
  objectId: string;
  evidenceIds: string[];
  text: LocalizedText;
};

export type SourceRecord = {
  id: string;
  title: string;
  publisher: string;
  officialUrl: string;
  date: string | null;
  locator: LocalizedText | null;
  license: string;
  attribution: string;
};

export type SearchEntry = {
  id: string;
  labels: LocalizedText;
  aliases: string[];
  normalizedKeys: string[];
};

export type LayoutNode = {
  artistId: string;
  x: number;
  y: number;
};

export type RightsRecord = {
  codeRights: LocalizedText;
  originalContentRights: LocalizedText;
  thirdPartyMetadata: LocalizedText[];
  mediaStatement: LocalizedText;
  mediaCount: number;
  mediaBytes: number;
  approvedMediaArtworks: number;
  noImageArtworks: number;
  mediaBundleId: string;
  mediaBundleHash: string;
  rightsRequestUrl: string;
  noticesPath: string;
  attributionsPath: string;
  withdrawalPath: string;
};

export type ThirdPartyNotice = {
  id: string;
  notice: string;
  sourceUrl: string | null;
  licenseIdentifiers: string[];
  attributions: string[];
};

export type GraphSummary = {
  releaseId: string;
  title: LocalizedText;
  artistCount: number;
  contextCount: number;
  relationshipCount: number;
  artworkCount: number;
  mediaCount: number;
  mediaBytes: number;
  approvedMediaArtworkCount: number;
  noImageArtworkCount: number;
  levelCounts: Record<"A" | "B" | "C", number>;
  relationshipTypeCounts: Record<RelationshipType, number>;
  semantics: LocalizedText;
  initialState: "artists_only";
};

export type ArtConstellationRelease = {
  manifestId: string;
  version: string;
  isPublicRelease: boolean;
  summary: GraphSummary;
  artists: ArtistRecord[];
  searchEntries: SearchEntry[];
  layout: LayoutNode[];
  facets: {
    periods: string[];
    regions: string[];
    traditions: string[];
    relationshipTypes: RelationshipType[];
  };
};

export type RelationshipIndex = {
  contexts: ContextRecord[];
  relationships: RelationshipRecord[];
};

export type RelationshipDetails = {
  relationship: RelationshipRecord;
  contexts: ContextRecord[];
  artworks: ArtworkRecord[];
  media: MediaAsset[];
  evidence: EvidenceRecord[];
  sources: SourceRecord[];
};

export type ArtistSources = {
  artist: ArtistRecord;
  artworks: ArtworkRecord[];
  media: MediaAsset[];
  sources: SourceRecord[];
};

export type ArtworkCatalog = {
  artworks: ArtworkRecord[];
  media: MediaAsset[];
};

export type ArtworkDetails = {
  artwork: ArtworkRecord;
  artist: ArtistRecord;
  media: MediaAsset[];
  claims: ClaimRecord[];
  evidence: EvidenceRecord[];
  sources: SourceRecord[];
};

export type RightsDetails = {
  rights: RightsRecord;
  notices: ThirdPartyNotice[];
};

export type DetailLoadResult<T> =
  | { status: "loaded"; data: T }
  | { status: "failed"; reason: string };

export type ArtConstellationDataSource = {
  loadRelationshipIndex: (signal?: AbortSignal) => Promise<DetailLoadResult<RelationshipIndex>>;
  loadArtworkCatalog: (signal?: AbortSignal) => Promise<DetailLoadResult<ArtworkCatalog>>;
  loadArtworkDetails: (artworkId: string, signal?: AbortSignal) => Promise<DetailLoadResult<ArtworkDetails>>;
  loadArtistSources: (artistId: string, signal?: AbortSignal) => Promise<DetailLoadResult<ArtistSources>>;
  loadRelationshipDetails: (
    relationshipId: string,
    signal?: AbortSignal,
  ) => Promise<DetailLoadResult<RelationshipDetails>>;
  loadRights: (signal?: AbortSignal) => Promise<DetailLoadResult<RightsDetails>>;
};

export function localize(value: LocalizedText, locale: Locale) {
  return locale === "zh-CN" ? value["zh-Hans"] : value.en;
}
