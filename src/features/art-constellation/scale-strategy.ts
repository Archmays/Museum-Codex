export const CONSTELLATION_GRAPH_NODE_LIMIT = 120;
export const CONSTELLATION_GRAPH_EDGE_LIMIT = 1_000;
export const CONSTELLATION_LIST_PAGE_SIZE = 50;
export const CONSTELLATION_TABLE_PAGE_SIZE = 100;

type StableEntity = { id: string };
type StableRelationship = {
  id: string;
  sourceArtistId: string;
  targetArtistId: string;
};

export type FocusedNeighbor<Artist, Relationship> = {
  artist: Artist;
  relationships: Relationship[];
  primaryLane: "shared_subject" | "shared_material" | "shared_technique";
};

type FocusedArtist = StableEntity & { labels: { "zh-Hans": string; en: string } };
type FocusedRelationship = StableRelationship & { type: "shared_subject" | "shared_material" | "shared_technique" };

export function planFocusedExplorer<Artist extends FocusedArtist, Relationship extends FocusedRelationship>(
  artists: Artist[],
  relationships: Relationship[],
  focusArtistId: string | null,
  locale: "zh-CN" | "en",
  expanded: boolean,
  initialNeighborLimit = 12,
  initialPerLaneLimit = 4,
  expandedNodeLimit = 20,
) {
  const artistById = new Map(artists.map((artist) => [artist.id, artist]));
  const focusArtist = focusArtistId ? artistById.get(focusArtistId) ?? null : null;
  if (!focusArtist) {
    return { focusArtist: null, neighbors: [] as FocusedNeighbor<Artist, Relationship>[], relationships: [] as Relationship[], hiddenDirectNeighborCount: 0, totalNodeCount: 0 };
  }
  const directById = new Map<string, Relationship[]>();
  for (const relationship of relationships) {
    const neighborId = relationship.sourceArtistId === focusArtistId
      ? relationship.targetArtistId
      : relationship.targetArtistId === focusArtistId
        ? relationship.sourceArtistId
        : null;
    if (neighborId && artistById.has(neighborId)) directById.set(neighborId, [...(directById.get(neighborId) ?? []), relationship]);
  }
  const label = (id: string) => artistById.get(id)!.labels[locale === "zh-CN" ? "zh-Hans" : "en"];
  const orderedDirect = [...directById.keys()].sort((left, right) => label(left).localeCompare(label(right), locale) || left.localeCompare(right));
  const laneOrder = ["shared_subject", "shared_material", "shared_technique"] as const;
  const selected: string[] = [];
  for (const lane of laneOrder) {
    for (const neighborId of orderedDirect) {
      if (selected.length >= initialNeighborLimit) break;
      const laneCount = selected.filter((id) => directById.get(id)?.some((relationship) => relationship.type === lane)).length;
      if (laneCount >= initialPerLaneLimit) break;
      if (!selected.includes(neighborId) && directById.get(neighborId)?.some((relationship) => relationship.type === lane)) selected.push(neighborId);
    }
  }
  for (const neighborId of orderedDirect) {
    if (selected.length >= initialNeighborLimit) break;
    if (!selected.includes(neighborId)) selected.push(neighborId);
  }
  if (expanded) {
    for (const neighborId of orderedDirect) {
      if (selected.length >= expandedNodeLimit - 1) break;
      if (!selected.includes(neighborId)) selected.push(neighborId);
    }
    const visible = new Set([focusArtistId, ...selected]);
    const secondHopIds = relationships.flatMap((relationship) => {
      if (visible.has(relationship.sourceArtistId) && !visible.has(relationship.targetArtistId)) return [relationship.targetArtistId];
      if (visible.has(relationship.targetArtistId) && !visible.has(relationship.sourceArtistId)) return [relationship.sourceArtistId];
      return [];
    }).filter((id) => artistById.has(id)).sort((left, right) => label(left).localeCompare(label(right), locale) || left.localeCompare(right));
    for (const id of secondHopIds) {
      if (selected.length >= expandedNodeLimit - 1) break;
      if (!selected.includes(id)) selected.push(id);
    }
  }
  const visibleIds = new Set([focusArtistId, ...selected]);
  const visibleRelationships = relationships.filter((relationship) => visibleIds.has(relationship.sourceArtistId) && visibleIds.has(relationship.targetArtistId));
  const neighbors = selected.map((id) => {
    const direct = directById.get(id) ?? visibleRelationships.filter((relationship) => relationship.sourceArtistId === id || relationship.targetArtistId === id);
    const primaryLane = laneOrder.find((lane) => direct.some((relationship) => relationship.type === lane)) ?? "shared_technique";
    return { artist: artistById.get(id)!, relationships: direct, primaryLane };
  });
  return {
    focusArtist,
    neighbors,
    relationships: visibleRelationships,
    hiddenDirectNeighborCount: Math.max(0, directById.size - selected.filter((id) => directById.has(id)).length),
    totalNodeCount: 1 + neighbors.length,
  };
}

export type ConstellationScalePlan<
  Artist extends StableEntity,
  Relationship extends StableRelationship,
> = {
  artists: Artist[];
  relationships: Relationship[];
  totalArtists: number;
  totalRelationships: number;
  limited: boolean;
  strategy: "complete_graph" | "focus_neighborhood_then_stable_id";
};

export function planConstellationGraph<
  Artist extends StableEntity,
  Relationship extends StableRelationship,
>(
  artists: Artist[],
  relationships: Relationship[],
  focusArtistId: string | null,
  nodeLimit = CONSTELLATION_GRAPH_NODE_LIMIT,
  edgeLimit = CONSTELLATION_GRAPH_EDGE_LIMIT,
): ConstellationScalePlan<Artist, Relationship> {
  if (artists.length <= nodeLimit && relationships.length <= edgeLimit) {
    return {
      artists,
      relationships,
      totalArtists: artists.length,
      totalRelationships: relationships.length,
      limited: false,
      strategy: "complete_graph",
    };
  }
  const artistById = new Map(artists.map((artist) => [artist.id, artist]));
  const orderedIds: string[] = [];
  const include = (id: string) => {
    if (artistById.has(id) && !orderedIds.includes(id) && orderedIds.length < nodeLimit) orderedIds.push(id);
  };
  if (focusArtistId) {
    include(focusArtistId);
    const neighbors = relationships
      .flatMap((relationship) => {
        if (relationship.sourceArtistId === focusArtistId) return [relationship.targetArtistId];
        if (relationship.targetArtistId === focusArtistId) return [relationship.sourceArtistId];
        return [];
      })
      .sort((left, right) => left.localeCompare(right));
    for (const id of neighbors) include(id);
  }
  for (const id of [...artistById.keys()].sort((left, right) => left.localeCompare(right))) include(id);
  const selected = new Set(orderedIds);
  const selectedRelationships = relationships
    .filter((relationship) =>
      selected.has(relationship.sourceArtistId) && selected.has(relationship.targetArtistId)
    )
    .sort((left, right) => left.id.localeCompare(right.id))
    .slice(0, edgeLimit);
  return {
    artists: orderedIds.map((id) => artistById.get(id)!),
    relationships: selectedRelationships,
    totalArtists: artists.length,
    totalRelationships: relationships.length,
    limited: true,
    strategy: "focus_neighborhood_then_stable_id",
  };
}

export function stablePage<Item>(
  items: Item[],
  requestedPage: number,
  pageSize: number,
) {
  const pageCount = Math.max(1, Math.ceil(items.length / pageSize));
  const page = Math.min(pageCount, Math.max(1, Math.trunc(requestedPage) || 1));
  const start = (page - 1) * pageSize;
  return {
    items: items.slice(start, start + pageSize),
    page,
    pageCount,
    pageSize,
    start,
    total: items.length,
  };
}
