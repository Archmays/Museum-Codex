import graphFixture from "../../public/releases/art-pathways-1.2.0/path-graph-input.json";
import indexFixture from "../../public/releases/art-pathways-1.2.0/path-index.json";
import { defaultPathQuery, findPathways, PATH_ALGORITHM_VERSION } from "../features/art-paths/path-algorithm";
import type { PathGraphInput, PathIndex, PathRelationship } from "../features/art-paths/types";

const graph = graphFixture as unknown as PathGraphInput;
const index = indexFixture as unknown as PathIndex;

describe("MUSEUM-06 Graphology bidirectional BFS and bounded Yen", () => {
  it("matches the Python build reference for all 66 default comparison pairs", () => {
    for (const pair of index.pairs) {
      const result = findPathways(graph, defaultPathQuery(pair.start_artist_id, pair.end_artist_id, "comparison"));
      const reference = pair.modes.comparison;
      expect(result.status, pair.pair_id).toBe(reference.status);
      expect(result.paths.map((path) => path.artist_ids), pair.pair_id).toEqual(reference.paths.map((path) => path.artist_ids));
      expect(result.paths.map((path) => path.relationship_ids), pair.pair_id).toEqual(reference.paths.map((path) => path.relationship_ids));
      expect(result.paths.map((path) => path.ranking_tuple), pair.pair_id).toEqual(reference.paths.map((path) => path.ranking_tuple));
    }
  });

  it("returns accurate empty historical and context modes for all pairs", () => {
    for (const pair of index.pairs) {
      expect(findPathways(graph, defaultPathQuery(pair.start_artist_id, pair.end_artist_id, "historical")).status).toBe("no_path_for_current_release_and_filters");
      expect(findPathways(graph, defaultPathQuery(pair.start_artist_id, pair.end_artist_id, "context")).status).toBe("no_path_for_current_release_and_filters");
    }
  });

  it("rejects invalid and identical endpoints distinctly", () => {
    const first = graph.artists[0].id;
    expect(findPathways(graph, defaultPathQuery("artist:missing", first, "comparison")).status).toBe("invalid_start");
    expect(findPathways(graph, defaultPathQuery(first, "artist:missing", "comparison")).status).toBe("invalid_end");
    expect(findPathways(graph, defaultPathQuery(first, first, "comparison")).status).toBe("same_endpoint");
  });

  it("separates search-budget exhaustion from no path", () => {
    const pair = index.pairs[0];
    const bounded = { ...defaultPathQuery(pair.start_artist_id, pair.end_artist_id, "comparison"), candidate_expansion_limit: 1 };
    expect(findPathways(graph, bounded)).toMatchObject({ status: "search_budget_reached", expansions_used: 1 });
    const emptyGraph = { ...graph, relationships: [], counts: { ...graph.counts, relationships: 0 } };
    expect(findPathways(emptyGraph, defaultPathQuery(pair.start_artist_id, pair.end_artist_id, "comparison")).status).toBe("no_path_for_current_release_and_filters");
  });

  it("honors maximum hops and relationship filters", () => {
    const multiHopPair = index.pairs.find((pair) => pair.modes.comparison.paths[0].hop_count > 1)!;
    expect(findPathways(graph, { ...defaultPathQuery(multiHopPair.start_artist_id, multiHopPair.end_artist_id, "comparison"), max_hops: 1 }).status).toBe("no_path_for_current_release_and_filters");
    const directPair = index.pairs.find((pair) => pair.modes.comparison.paths[0].hop_count === 1)!;
    const usedType = directPair.modes.comparison.paths[0].steps[0].relationship_type;
    expect(findPathways(graph, { ...defaultPathQuery(directPair.start_artist_id, directPair.end_artist_id, "comparison"), allowed_relationship_types: [usedType] }).status).toBe("ready");
    expect(findPathways(graph, { ...defaultPathQuery(directPair.start_artist_id, directPair.end_artist_id, "comparison"), allowed_relationship_types: ["not_present"] }).status).toBe("no_path_for_current_release_and_filters");
  });

  it("excludes withdrawn, deprecated, unreviewed, hidden, and algorithmic edges before search", () => {
    const pair = index.pairs.find((candidate) => candidate.modes.comparison.paths[0].hop_count === 1)!;
    const edgeId = pair.modes.comparison.paths[0].relationship_ids[0];
    for (const mutation of [
      { withdrawn: true }, { deprecated: true }, { public_display: false }, { review_status: "draft" },
      { is_algorithmic: true, computational_similarity: 0.8 },
    ]) {
      const relationships = graph.relationships.map((edge) => edge.id === edgeId ? { ...edge, ...mutation } as PathRelationship : edge);
      const result = findPathways({ ...graph, relationships }, defaultPathQuery(pair.start_artist_id, pair.end_artist_id, "comparison"));
      expect(result.paths.some((path) => path.relationship_ids.includes(edgeId))).toBe(false);
    }
  });

  it("uses directed Graphology edges only in the allowed direction", () => {
    const [a, b] = graph.artists.slice(0, 2);
    const base = graph.relationships[0];
    const directed = { ...base, id: "art-rel:directed-test", source_artist_id: a.id, target_artist_id: b.id, level: "A", directed: true } as PathRelationship;
    const directedGraph = { ...graph, artists: [a, b], relationships: [directed] };
    expect(findPathways(directedGraph, defaultPathQuery(a.id, b.id, "historical")).status).toBe("ready");
    expect(findPathways(directedGraph, defaultPathQuery(b.id, a.id, "historical")).status).toBe("no_path_for_current_release_and_filters");
  });

  it("returns at most three unique loopless alternatives with stable output", () => {
    const pair = index.pairs[0];
    const query = defaultPathQuery(pair.start_artist_id, pair.end_artist_id, "comparison");
    const first = findPathways(graph, query);
    const second = findPathways(graph, query);
    expect(first).toEqual(second);
    expect(first.paths).toHaveLength(3);
    expect(new Set(first.paths.map((path) => path.relationship_ids.join("|"))).size).toBe(3);
    expect(first.paths.every((path) => new Set(path.artist_ids).size === path.artist_ids.length)).toBe(true);
    expect(first.algorithm_version).toBe(PATH_ALGORITHM_VERSION);
  });
});
