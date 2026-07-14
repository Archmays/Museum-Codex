import type {
  ArtConstellationRelease,
  ArtistRecord,
  RelationshipIndex,
  RelationshipRecord,
  RelationshipType,
  SearchEntry,
  ViewMode,
} from "./types";

export type ConstellationState = {
  view: ViewMode;
  query: string;
  relationshipType: RelationshipType | "all";
  level: "all" | "A" | "B" | "C";
  period: string;
  region: string;
  tradition: string;
  contextType: string;
  focusArtistId: string | null;
  selectedRelationshipId: string | null;
};

export type ConstellationDerivationState = Omit<ConstellationState, "view">;

export type ConstellationAction =
  | { type: "set-view"; view: ViewMode }
  | { type: "set-query"; query: string }
  | { type: "set-relationship-type"; relationshipType: RelationshipType | "all" }
  | { type: "set-level"; level: ConstellationState["level"] }
  | { type: "set-period"; period: string }
  | { type: "set-region"; region: string }
  | { type: "set-tradition"; tradition: string }
  | { type: "set-context-type"; contextType: string }
  | { type: "focus-artist"; artistId: string | null }
  | { type: "select-relationship"; relationshipId: string | null }
  | { type: "reset" };

const VIEW_MODES = new Set<ViewMode>(["graph", "list", "table"]);
const RELATIONSHIP_TYPES = new Set<RelationshipType>([
  "shared_material",
  "shared_subject",
  "shared_technique",
]);

export function createConstellationState(
  params: URLSearchParams,
  release: ArtConstellationRelease,
): ConstellationState {
  const requestedView = params.get("view") as ViewMode | null;
  const requestedType = (params.get("types") ?? params.get("type")) as RelationshipType | null;
  const requestedLevel = params.get("level") as ConstellationState["level"] | null;
  const requestedArtist = params.get("focus") ?? params.get("artist");
  const requestedRelationship = params.get("relation");
  return {
    view: requestedView && VIEW_MODES.has(requestedView) ? requestedView : "graph",
    query: params.get("q")?.slice(0, 120) ?? "",
    relationshipType: requestedType && RELATIONSHIP_TYPES.has(requestedType) ? requestedType : "all",
    level: requestedLevel && new Set(["all", "A", "B", "C"]).has(requestedLevel) ? requestedLevel : "all",
    period: release.facets.periods.includes(params.get("period") ?? "") ? (params.get("period") ?? "") : "",
    region: release.facets.regions.includes(params.get("region") ?? "") ? (params.get("region") ?? "") : "",
    tradition: release.facets.traditions.includes(params.get("tradition") ?? "") ? (params.get("tradition") ?? "") : "",
    contextType: params.get("context")?.slice(0, 80) ?? "",
    focusArtistId: release.artists.some((artist) => artist.id === requestedArtist) ? requestedArtist : null,
    selectedRelationshipId: requestedRelationship && /^(?:art-rel|relationship):[a-z0-9._:-]+$/i.test(requestedRelationship)
      ? requestedRelationship
      : null,
  };
}

export function constellationReducer(
  state: ConstellationState,
  action: ConstellationAction,
): ConstellationState {
  switch (action.type) {
    case "set-view":
      return { ...state, view: action.view };
    case "set-query":
      return { ...state, query: action.query.slice(0, 120), focusArtistId: null, selectedRelationshipId: null };
    case "set-relationship-type":
      return { ...state, relationshipType: action.relationshipType, selectedRelationshipId: null };
    case "set-level":
      return { ...state, level: action.level, selectedRelationshipId: null };
    case "set-period":
      return { ...state, period: action.period, focusArtistId: null, selectedRelationshipId: null };
    case "set-region":
      return { ...state, region: action.region, focusArtistId: null, selectedRelationshipId: null };
    case "set-tradition":
      return { ...state, tradition: action.tradition, focusArtistId: null, selectedRelationshipId: null };
    case "set-context-type":
      return { ...state, contextType: action.contextType, selectedRelationshipId: null };
    case "focus-artist":
      return { ...state, focusArtistId: action.artistId, selectedRelationshipId: null };
    case "select-relationship":
      return { ...state, selectedRelationshipId: action.relationshipId };
    case "reset":
      return {
        view: state.view,
        query: "",
        relationshipType: "all",
        level: "all",
        period: "",
        region: "",
        tradition: "",
        contextType: "",
        focusArtistId: null,
        selectedRelationshipId: null,
      };
  }
}

export function stateToSearchParams(state: ConstellationState, releaseVersion?: string) {
  const params = new URLSearchParams();
  if (releaseVersion) params.set("release", releaseVersion);
  if (state.view !== "graph") params.set("view", state.view);
  if (state.query.trim()) params.set("q", state.query.trim());
  if (state.relationshipType !== "all") params.set("types", state.relationshipType);
  if (state.level !== "all") params.set("level", state.level);
  if (state.period) params.set("period", state.period);
  if (state.region) params.set("region", state.region);
  if (state.tradition) params.set("tradition", state.tradition);
  if (state.contextType) params.set("context", state.contextType);
  if (state.focusArtistId) params.set("focus", state.focusArtistId);
  if (state.selectedRelationshipId) params.set("relation", state.selectedRelationshipId);
  return params;
}

export function normalizeSearch(value: string) {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase()
    .replace(/[\p{P}\p{S}\s]+/gu, " ")
    .trim();
}

export type MatchReason = "exact" | "prefix" | "substring" | "alias";

function findMatchReason(artist: ArtistRecord, entry: SearchEntry | undefined, query: string): MatchReason | null {
  if (!query) return null;
  const preferred = [artist.labels["zh-Hans"], artist.labels.en].map(normalizeSearch);
  const aliases = [...artist.aliases, ...(entry?.aliases ?? [])].map(normalizeSearch);
  if (preferred.includes(query)) return "exact";
  if (preferred.some((value) => value.startsWith(query))) return "prefix";
  if (preferred.some((value) => value.includes(query))) return "substring";
  if (aliases.some((value) => value === query || value.startsWith(query) || value.includes(query))) return "alias";
  if (entry?.normalizedKeys.some((value) => normalizeSearch(value).includes(query))) return "alias";
  return null;
}

export type ConstellationViewModel = {
  artists: ArtistRecord[];
  relationships: RelationshipRecord[];
  graphRelationships: RelationshipRecord[];
  matchReasons: Map<string, MatchReason>;
  hiddenArtistCount: number;
  hiddenRelationshipCount: number;
  relatedArtistIds: Set<string>;
};

export function deriveConstellationView(
  release: ArtConstellationRelease,
  relationshipIndex: RelationshipIndex | null,
  state: ConstellationDerivationState,
): ConstellationViewModel {
  const baseArtists = release.artists.filter(
    (artist) =>
      (!state.period || artist.period === state.period) &&
      (!state.region || artist.region === state.region) &&
      (!state.tradition || artist.tradition === state.tradition),
  );
  const baseIds = new Set(baseArtists.map((artist) => artist.id));
  const contextIds = state.contextType
    ? new Set(relationshipIndex?.contexts.filter((context) => context.type === state.contextType).map((context) => context.id) ?? [])
    : null;
  const typeRelationships = (relationshipIndex?.relationships ?? []).filter(
    (relationship) =>
      (state.level === "all" || state.level === "C") &&
      (state.relationshipType === "all" || relationship.type === state.relationshipType) &&
      (!contextIds || relationship.contextIds.some((id) => contextIds.has(id))) &&
      baseIds.has(relationship.sourceArtistId) &&
      baseIds.has(relationship.targetArtistId),
  );
  const normalizedQuery = normalizeSearch(state.query);
  const matchReasons = new Map<string, MatchReason>();
  const searchById = new Map(release.searchEntries.map((entry) => [entry.id, entry]));
  for (const artist of baseArtists) {
    const reason = findMatchReason(artist, searchById.get(artist.id), normalizedQuery);
    if (reason) matchReasons.set(artist.id, reason);
  }

  let visibleIds = new Set(baseIds);
  if (normalizedQuery) {
    visibleIds = new Set(matchReasons.keys());
  }
  if (state.focusArtistId && baseIds.has(state.focusArtistId)) {
    visibleIds.add(state.focusArtistId);
    for (const relationship of typeRelationships) {
      if (relationship.sourceArtistId === state.focusArtistId) visibleIds.add(relationship.targetArtistId);
      if (relationship.targetArtistId === state.focusArtistId) visibleIds.add(relationship.sourceArtistId);
    }
  }

  const artists = baseArtists.filter((artist) => visibleIds.has(artist.id));
  const relationships = typeRelationships.filter(
    (relationship) => visibleIds.has(relationship.sourceArtistId) && visibleIds.has(relationship.targetArtistId),
  );
  const graphRelationships = state.focusArtistId
    ? relationships.filter(
        (relationship) =>
          relationship.sourceArtistId === state.focusArtistId || relationship.targetArtistId === state.focusArtistId,
      )
    : [];
  const relatedArtistIds = new Set<string>();
  if (state.focusArtistId) {
    relatedArtistIds.add(state.focusArtistId);
    for (const relationship of graphRelationships) {
      relatedArtistIds.add(relationship.sourceArtistId);
      relatedArtistIds.add(relationship.targetArtistId);
    }
  }

  return {
    artists,
    relationships,
    graphRelationships,
    matchReasons,
    hiddenArtistCount: release.artists.length - artists.length,
    hiddenRelationshipCount: release.summary.relationshipCount - relationships.length,
    relatedArtistIds,
  };
}
