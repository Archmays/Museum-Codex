import Graph from "graphology";
import type {
  ArtistPath,
  PathArtist,
  PathGraphInput,
  PathMode,
  PathQuery,
  PathRelationship,
  PathResult,
  PathStep,
} from "./types";

export const PATH_ALGORITHM_VERSION = "museum-paths-bibfs-yen-1.0.0" as const;
export const PATH_RELEASE_ID = "release:art-pathways-1.2.0" as const;
const MODE_LEVELS = { historical: new Set(["A", "B"]), context: new Set(["B"]), comparison: new Set(["C"]) } as const;
const DISCLAIMERS = {
  historical: { "zh-Hans": "最短 hop 路径只描述当前 release 中经审核的历史关系，不是唯一或真实的历史传播链。", en: "The shortest-hop path describes reviewed historical relations in this release; it is not a unique or actual chain of transmission." },
  context: { "zh-Hans": "语境路径只显示共享的具体历史语境，不推出艺术家直接接触或影响。", en: "A context path shows only a shared specific historical context and does not infer direct contact or influence." },
  comparison: { "zh-Hans": "C｜策展比较：路径不证明艺术家相识、影响、师承或传播。", en: "C | Curatorial comparison: this path does not prove acquaintance, influence, instruction, or transmission." },
} as const;
const NO_PATH = { "zh-Hans": "当前 release 和筛选条件下没有可展示路径，不代表现实中不存在关系。", en: "No displayable path exists in the current release under these filters; this does not mean no relationship exists in reality." };

type Candidate = { artistIds: string[]; relationshipIds: string[] };
type Adjacent = Map<string, Array<{ neighbor: string; edgeId: string }>>;

class BudgetReached extends Error {}
class Budget {
  used = 0;
  readonly limit: number;
  constructor(limit: number) { this.limit = limit; }
  expand() {
    if (this.used >= this.limit) throw new BudgetReached();
    this.used += 1;
  }
}

export function defaultPathQuery(start: string, end: string, mode: PathMode): PathQuery {
  return {
    schema_version: "1.0.0",
    fixed_release_id: PATH_RELEASE_ID,
    start_artist_id: start,
    end_artist_id: end,
    mode,
    allowed_relationship_types: [],
    allowed_levels: [...MODE_LEVELS[mode]] as Array<"A" | "B" | "C">,
    period_filter: null,
    region_filter: null,
    direction_policy: "respect_semantic_direction",
    max_hops: 6,
    k: 3,
    candidate_expansion_limit: 10_000,
  };
}

export function findPathways(graphInput: PathGraphInput, query: PathQuery): PathResult {
  const result = emptyResult(graphInput.graph_hash, query);
  const artists = new Map(graphInput.artists.map((artist) => [artist.id, artist]));
  const start = query.start_artist_id;
  const end = query.end_artist_id;
  if (query.fixed_release_id !== PATH_RELEASE_ID) return { ...result, status: "incompatible_release" };
  if (!artists.has(start)) return { ...result, status: "invalid_start" };
  if (!artists.has(end)) return { ...result, status: "invalid_end" };
  if (start === end) return { ...result, status: "same_endpoint" };
  if (artists.get(start)?.withdrawn || artists.get(end)?.withdrawn) return { ...result, status: "withdrawn_endpoint" };
  if (query.max_hops < 1 || query.max_hops > 6 || query.k < 1 || query.k > 3 || query.candidate_expansion_limit < 1 || query.candidate_expansion_limit > 10_000) {
    return result;
  }
  const filtered = filterEdges(graphInput.relationships, query);
  const edgeById = new Map(filtered.map((edge) => [edge.id, edge]));
  const { forward, reverse } = buildAdjacency(graphInput.artists, filtered);
  const budget = new Budget(query.candidate_expansion_limit);
  const accepted: Candidate[] = [];
  const candidates = new Map<string, Candidate>();
  let budgetReached = false;
  try {
    const first = bidirectionalShortest(start, end, forward, reverse, edgeById, artists, query.max_hops, budget);
    if (!first) return { ...result, status: "no_path_for_current_release_and_filters", expansions_used: budget.used, disclaimer: NO_PATH };
    accepted.push(first);
    while (accepted.length < query.k) {
      const previous = accepted[accepted.length - 1];
      for (let spurIndex = 0; spurIndex < previous.artistIds.length - 1; spurIndex += 1) {
        const rootNodes = previous.artistIds.slice(0, spurIndex + 1);
        const rootEdges = previous.relationshipIds.slice(0, spurIndex);
        const removedEdges = new Set<string>();
        for (const path of accepted) {
          if (sameArray(path.artistIds.slice(0, spurIndex + 1), rootNodes) && path.relationshipIds[spurIndex]) {
            removedEdges.add(path.relationshipIds[spurIndex]);
          }
        }
        const spur = bidirectionalShortest(
          rootNodes[rootNodes.length - 1], end, forward, reverse, edgeById, artists,
          query.max_hops - rootEdges.length, budget, new Set(rootNodes.slice(0, -1)), removedEdges,
        );
        if (!spur) continue;
        const combined = { artistIds: [...rootNodes.slice(0, -1), ...spur.artistIds], relationshipIds: [...rootEdges, ...spur.relationshipIds] };
        if (new Set(combined.artistIds).size !== combined.artistIds.length) continue;
        const identity = candidateIdentity(combined);
        if (!accepted.some((path) => candidateIdentity(path) === identity)) candidates.set(identity, combined);
      }
      const next = [...candidates.entries()].sort((left, right) => compareCandidate(left[1], right[1], edgeById, artists))[0];
      if (!next) break;
      candidates.delete(next[0]);
      accepted.push(next[1]);
    }
  } catch (error) {
    if (error instanceof BudgetReached) budgetReached = true;
    else return result;
  }
  accepted.sort((left, right) => compareCandidate(left, right, edgeById, artists));
  return {
    ...result,
    status: budgetReached ? "search_budget_reached" : "ready",
    paths: accepted.slice(0, query.k).map((candidate, index) => serializePath(candidate, index + 1, edgeById, artists, query)),
    expansions_used: budget.used,
  };
}

function filterEdges(edges: PathRelationship[], query: PathQuery) {
  const modeLevels = MODE_LEVELS[query.mode];
  const requestedLevels = new Set(query.allowed_levels.length ? query.allowed_levels : [...modeLevels]);
  const requestedTypes = new Set(query.allowed_relationship_types);
  const periods = new Set(query.period_filter ?? []);
  const regions = new Set((query.region_filter ?? []).map((value) => value.toLocaleLowerCase()));
  return [...edges].sort((left, right) => left.id.localeCompare(right.id)).filter((edge) =>
    edge.release_id === PATH_RELEASE_ID && edge.public_display &&
    (edge.review_status === "verified" || edge.review_status === "publishable") &&
    !edge.withdrawn && edge.lifecycle_status !== "withdrawn" && !edge.deprecated && edge.lifecycle_status !== "deprecated" &&
    edge.rights_visibility === "public" && modeLevels.has(edge.level) && requestedLevels.has(edge.level) &&
    (!requestedTypes.size || requestedTypes.has(edge.type)) &&
    (!periods.size || edge.periods.some((value) => periods.has(value))) &&
    (!regions.size || edge.regions.some((value) => regions.has(value.toLocaleLowerCase()))) &&
    edge.is_algorithmic === false && edge.computational_similarity === null
  );
}

function buildAdjacency(artists: PathArtist[], edges: PathRelationship[]) {
  const graph = new Graph({ type: "mixed", multi: true, allowSelfLoops: false });
  artists.forEach((artist) => graph.addNode(artist.id));
  edges.forEach((edge) => {
    if (!graph.hasNode(edge.source_artist_id) || !graph.hasNode(edge.target_artist_id)) return;
    if (edge.directed) graph.addDirectedEdgeWithKey(edge.id, edge.source_artist_id, edge.target_artist_id, { relationshipId: edge.id });
    else graph.addUndirectedEdgeWithKey(edge.id, edge.source_artist_id, edge.target_artist_id, { relationshipId: edge.id });
  });
  const forward: Adjacent = new Map(artists.map((artist) => [artist.id, []]));
  const reverse: Adjacent = new Map(artists.map((artist) => [artist.id, []]));
  graph.forEachEdge((key, _attributes, source, target, _sourceAttributes, _targetAttributes, undirected) => {
    forward.get(source)?.push({ neighbor: target, edgeId: key });
    reverse.get(target)?.push({ neighbor: source, edgeId: key });
    if (undirected) {
      forward.get(target)?.push({ neighbor: source, edgeId: key });
      reverse.get(source)?.push({ neighbor: target, edgeId: key });
    }
  });
  for (const adjacency of [forward, reverse]) {
    adjacency.forEach((values) => values.sort((left, right) => left.edgeId.localeCompare(right.edgeId) || left.neighbor.localeCompare(right.neighbor)));
  }
  return { forward, reverse };
}

function bidirectionalShortest(
  start: string,
  end: string,
  forward: Adjacent,
  reverse: Adjacent,
  edges: Map<string, PathRelationship>,
  artists: Map<string, PathArtist>,
  maxHops: number,
  budget: Budget,
  bannedNodes = new Set<string>(),
  bannedEdges = new Set<string>(),
): Candidate | null {
  if (bannedNodes.has(start) || bannedNodes.has(end) || maxHops < 1) return null;
  const forwardDistance = boundedDistances(start, forward, maxHops, budget, bannedNodes, bannedEdges);
  const distance = forwardDistance.get(end);
  if (distance === undefined) return null;
  const reverseDistance = boundedDistances(end, reverse, distance, budget, bannedNodes, bannedEdges);
  const paths: Candidate[] = [];
  const visit = (node: string, artistIds: string[], relationshipIds: string[]) => {
    if (relationshipIds.length === distance) {
      if (node === end) paths.push({ artistIds, relationshipIds });
      return;
    }
    for (const adjacent of forward.get(node) ?? []) {
      budget.expand();
      if (bannedEdges.has(adjacent.edgeId) || bannedNodes.has(adjacent.neighbor) || artistIds.includes(adjacent.neighbor)) continue;
      if (forwardDistance.get(adjacent.neighbor) !== relationshipIds.length + 1) continue;
      if (reverseDistance.get(adjacent.neighbor) !== distance - relationshipIds.length - 1) continue;
      visit(adjacent.neighbor, [...artistIds, adjacent.neighbor], [...relationshipIds, adjacent.edgeId]);
    }
  };
  visit(start, [start], []);
  return paths.sort((left, right) => compareCandidate(left, right, edges, artists))[0] ?? null;
}

function boundedDistances(start: string, adjacency: Adjacent, maxHops: number, budget: Budget, bannedNodes: Set<string>, bannedEdges: Set<string>) {
  const distance = new Map([[start, 0]]);
  const queue = [start];
  while (queue.length) {
    const node = queue.shift() as string;
    if ((distance.get(node) ?? 0) >= maxHops) continue;
    for (const adjacent of adjacency.get(node) ?? []) {
      budget.expand();
      if (bannedEdges.has(adjacent.edgeId) || bannedNodes.has(adjacent.neighbor) || distance.has(adjacent.neighbor)) continue;
      distance.set(adjacent.neighbor, (distance.get(node) ?? 0) + 1);
      queue.push(adjacent.neighbor);
    }
  }
  return distance;
}

function candidateTuple(candidate: Candidate, edges: Map<string, PathRelationship>, artists: Map<string, PathArtist>) {
  const pathEdges = candidate.relationshipIds.map((id) => edges.get(id) as PathRelationship);
  const confidence = pathEdges.reduce((total, edge) => total + edge.evidence_confidence, 0) / pathEdges.length;
  const coherence = timeCoherence(candidate.artistIds, artists);
  const typeCounts = new Map<string, number>();
  pathEdges.forEach((edge) => typeCounts.set(edge.type, (typeCounts.get(edge.type) ?? 0) + 1));
  const repetitions = [...typeCounts.values()].reduce((total, count) => total + Math.max(0, count - 1), 0);
  return {
    hopCount: pathEdges.length,
    levelRank: Math.min(...pathEdges.map((edge) => ({ A: 1, B: 2, C: 3 })[edge.level])),
    confidenceDesc: -Number(confidence.toFixed(6)),
    coherencePenalty: ({ coherent: 0, mixed: 1, discontinuous: 2 } as const)[coherence],
    repetitions,
    relationKey: candidate.relationshipIds.join("\u0000"),
    artistKey: candidate.artistIds.join("\u0000"),
    coherence,
    confidence,
  };
}

function compareCandidate(left: Candidate, right: Candidate, edges: Map<string, PathRelationship>, artists: Map<string, PathArtist>) {
  const a = candidateTuple(left, edges, artists);
  const b = candidateTuple(right, edges, artists);
  return a.hopCount - b.hopCount || a.levelRank - b.levelRank || a.confidenceDesc - b.confidenceDesc ||
    a.coherencePenalty - b.coherencePenalty || a.repetitions - b.repetitions ||
    a.relationKey.localeCompare(b.relationKey) || a.artistKey.localeCompare(b.artistKey);
}

function timeCoherence(artistIds: string[], artists: Map<string, PathArtist>): "coherent" | "mixed" | "discontinuous" {
  const spans = artistIds.map((id) => artists.get(id)?.life_span).filter((span): span is { birth_year: number; death_year: number } =>
    typeof span?.birth_year === "number" && typeof span.death_year === "number"
  );
  if (spans.length < 2) return "mixed";
  if (Math.max(...spans.map((span) => span.birth_year)) <= Math.min(...spans.map((span) => span.death_year))) return "coherent";
  spans.sort((left, right) => left.birth_year - right.birth_year);
  const gaps = spans.slice(1).map((span, index) => Math.max(0, span.birth_year - spans[index].death_year));
  return Math.max(...gaps) <= 50 ? "mixed" : "discontinuous";
}

function serializePath(candidate: Candidate, rank: number, edges: Map<string, PathRelationship>, artists: Map<string, PathArtist>, query: PathQuery): ArtistPath {
  const pathEdges = candidate.relationshipIds.map((id) => edges.get(id) as PathRelationship);
  const tuple = candidateTuple(candidate, edges, artists);
  const steps: PathStep[] = pathEdges.map((edge, index) => ({
    sequence: index + 1,
    source_artist_id: candidate.artistIds[index],
    target_artist_id: candidate.artistIds[index + 1],
    relationship_id: edge.id,
    direction: edge.directed ? "directed_forward" : "undirected",
    relationship_type: edge.type,
    level: edge.level,
    context_ids: edge.context_ids,
    claim_ids: edge.claim_ids,
    evidence_ids: edge.evidence_ids,
    source_ids: edge.source_ids,
    supporting_artwork_ids: edge.supporting_artwork_ids,
    evidence_confidence: edge.evidence_confidence,
    why_connected: edge.why_connected,
    does_not_prove: edge.does_not_prove,
    rights_attribution: edge.rights_attribution,
    withdrawal_status: "active",
  }));
  const slug = [query.start_artist_id, query.end_artist_id].map((id) => id.split(":")[1]).join("--");
  return {
    id: `path:${slug}-${query.mode}-${String(rank).padStart(2, "0")}`,
    rank,
    hop_count: pathEdges.length,
    artist_ids: candidate.artistIds,
    relationship_ids: candidate.relationshipIds,
    steps,
    evidence_level: pathEdges[0].level,
    evidence_confidence: Number(tuple.confidence.toFixed(6)),
    time_coherence: tuple.coherence,
    relation_type_repeat_count: tuple.repetitions,
    ranking_tuple: {
      hop_count: tuple.hopCount,
      evidence_level_rank: tuple.levelRank,
      evidence_confidence_desc: tuple.confidenceDesc,
      time_coherence_penalty: tuple.coherencePenalty,
      relation_type_repeat_count: tuple.repetitions,
      stable_relation_id_sequence: candidate.relationshipIds,
      stable_artist_id_sequence: candidate.artistIds,
    },
  };
}

function emptyResult(graphHash: string, query: PathQuery): PathResult {
  return {
    schema_version: "1.0.0",
    id: `path-result:${query.start_artist_id.replace(":", "-")}--${query.end_artist_id.replace(":", "-")}--${query.mode}`,
    entity_type: "art_path_result",
    release_id: PATH_RELEASE_ID,
    algorithm_version: PATH_ALGORITHM_VERSION,
    input_graph_hash: graphHash,
    status: "runtime_calculation_failed",
    query,
    paths: [],
    expansions_used: 0,
    disclaimer: DISCLAIMERS[query.mode],
  };
}

function sameArray(left: string[], right: string[]) {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function candidateIdentity(candidate: Candidate) {
  return `${candidate.artistIds.join("|")}::${candidate.relationshipIds.join("|")}`;
}
