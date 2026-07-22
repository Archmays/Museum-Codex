import type { MatchReason, SearchRecord, SearchResult, SearchValue } from "./types";

export function normalizeSearchText(value: string) {
  return value
    .normalize("NFKC")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/\p{M}+/gu, "")
    .replace(/[^\p{L}\p{N}_]+/gu, " ")
    .trim()
    .replace(/\s+/g, " ");
}

type SegmenterLike = {
  segment: (value: string) => Iterable<{ segment: string; isWordLike?: boolean }>;
};

const segmenterCache = new Map<string, SegmenterLike | null>();
const tokenCache = new WeakMap<SearchValue, Map<string, Set<string>>>();

function createSegmenter(locale: string): SegmenterLike | null {
  if (segmenterCache.has(locale)) return segmenterCache.get(locale) ?? null;
  const constructor = (Intl as unknown as {
    Segmenter?: new (locale?: string, options?: { granularity: "word" }) => SegmenterLike;
  }).Segmenter;
  if (!constructor) {
    segmenterCache.set(locale, null);
    return null;
  }
  try {
    const segmenter = new constructor(locale, { granularity: "word" });
    segmenterCache.set(locale, segmenter);
    return segmenter;
  } catch {
    segmenterCache.set(locale, null);
    return null;
  }
}

function tokenMatches(value: SearchValue, query: string, locale: string, segmenter: SegmenterLike | null) {
  if (!segmenter) return false;
  let byLocale = tokenCache.get(value);
  if (!byLocale) {
    byLocale = new Map();
    tokenCache.set(value, byLocale);
  }
  let tokens = byLocale.get(locale);
  if (!tokens) {
    tokens = new Set(
      [...segmenter.segment(value.text)]
        .filter((item) => item.isWordLike !== false)
        .map((item) => normalizeSearchText(item.segment))
        .filter(Boolean),
    );
    byLocale.set(locale, tokens);
  }
  return tokens.has(query);
}

function classifyMatch(
  value: SearchValue,
  query: string,
  locale: string,
  segmenter: SegmenterLike | null,
): { rank: number; reason: MatchReason } | null {
  if (value.normalized === query) {
    return value.reason === "preferred"
      ? { rank: 0, reason: "exact_preferred" }
      : { rank: 1, reason: "exact_alias" };
  }
  if (value.normalized.startsWith(query)) return { rank: 2, reason: "prefix" };
  if (tokenMatches(value, query, locale, segmenter)) return { rank: 3, reason: "segmenter_token" };
  if (value.normalized.includes(query)) return { rank: 4, reason: "substring" };
  return null;
}

export function searchRecords(
  records: SearchRecord[],
  rawQuery: string,
  locale: "zh-CN" | "en",
): SearchResult[] {
  const query = normalizeSearchText(rawQuery);
  if (!query) return [];
  const segmenterLocale = locale === "zh-CN" ? "zh-Hans" : "en";
  const segmenter = createSegmenter(segmenterLocale);
  const results: SearchResult[] = [];
  for (const record of records) {
    if (record.withdrawal_status !== "active") continue;
    let best: { rank: number; reason: MatchReason; value: SearchValue } | null = null;
    for (const value of record.values) {
      const match = classifyMatch(value, query, segmenterLocale, segmenter);
      if (
        match &&
        (
          !best ||
          match.rank < best.rank ||
          (match.rank === best.rank && value.normalized.localeCompare(best.value.normalized) < 0)
        )
      ) {
        best = { ...match, value };
      }
    }
    if (!best) continue;
    results.push({
      record,
      matchReason: best.reason,
      matchedValue: best.value,
      rankTuple: [best.rank, record.visitor_task_order, record.stable_id],
    });
  }
  return results.sort((left, right) =>
    left.rankTuple[0] - right.rankTuple[0] ||
    left.rankTuple[1] - right.rankTuple[1] ||
    left.rankTuple[2].localeCompare(right.rankTuple[2])
  );
}
