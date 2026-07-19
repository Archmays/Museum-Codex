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
