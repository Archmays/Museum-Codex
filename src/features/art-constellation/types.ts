import type { Locale } from "../../i18n/translations";

export type LocalizedText = {
  "zh-Hans": string;
  en: string;
};

export type ViewMode = "graph" | "list" | "table";
export type RelationshipType = "shared_material" | "shared_subject" | "shared_technique";

export type ArtistRecord = {
  id: string;
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
};

export type EvidenceRecord = {
  id: string;
  sourceIds: string[];
  summary: LocalizedText;
  locator: string | null;
  reliabilityNote: LocalizedText;
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
  noMedia: true;
  rightsRequestUrl: string;
  noticesPath: string;
  attributionsPath: string;
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
  artistCount: 12;
  contextCount: 31;
  relationshipCount: 36;
  artworkCount: number;
  levelCounts: { A: 0; B: 0; C: 36 };
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
  evidence: EvidenceRecord[];
  sources: SourceRecord[];
};

export type ArtistSources = {
  artist: ArtistRecord;
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
