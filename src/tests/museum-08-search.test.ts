import { afterEach, describe, expect, it } from "vitest";
import { normalizeSearchText, searchRecords } from "../features/art-search/search-model";
import type { SearchRecord } from "../features/art-search/types";

function record(
  stableId: string,
  entityType: SearchRecord["entity_type"],
  order: number,
  values: SearchRecord["values"],
  withdrawal: SearchRecord["withdrawal_status"] = "active",
): SearchRecord {
  return {
    id: `search-record:${stableId.replaceAll(":", "-")}`,
    stable_id: stableId,
    entity_type: entityType,
    route: "/art",
    labels: { "zh-Hans": values[0].text, en: values[0].text },
    description: { "zh-Hans": "说明", en: "Description" },
    values,
    visitor_task_order: order,
    withdrawal_status: withdrawal,
  };
}

const preferred = (text: string, language = "en") => ({
  text,
  normalized: normalizeSearchText(text),
  language,
  reason: "preferred" as const,
});

const alias = (text: string, reason: "approved_alias" | "transliteration" | "source_language") => ({
  text,
  normalized: normalizeSearchText(text),
  language: "en",
  reason,
});

const originalSegmenter = Object.getOwnPropertyDescriptor(Intl, "Segmenter");

afterEach(() => {
  if (originalSegmenter) Object.defineProperty(Intl, "Segmenter", originalSegmenter);
});

describe("MUSEUM-08 deterministic local search", () => {
  it("normalizes Unicode, punctuation, case, and diacritics deterministically", () => {
    expect(normalizeSearchText("  Albrecht DÜRER  ")).toBe("albrecht durer");
    expect(normalizeSearchText("阿尔布雷希特·丢勒")).toBe("阿尔布雷希特 丢勒");
    expect(normalizeSearchText("Café")).toBe("cafe");
  });

  it("supports exact, prefix, substring, approved alias, transliteration, and source-language labels", () => {
    const records = [
      record("artist:durer", "artist", 0, [
        preferred("阿尔布雷希特·丢勒", "zh-Hans"),
        preferred("Albrecht Dürer"),
        alias("Albrecht Duerer", "transliteration"),
        alias("Dürer, Albrecht", "approved_alias"),
        alias("Albrecht Dürer der Ältere", "source_language"),
      ]),
    ];
    expect(searchRecords(records, "阿尔布雷希特·丢勒", "zh-CN")[0].matchReason).toBe("exact_preferred");
    expect(searchRecords(records, "Albrecht Duerer", "en")[0].matchReason).toBe("exact_alias");
    expect(searchRecords(records, "Albrecht D", "en")[0].matchReason).toBe("prefix");
    expect(searchRecords(records, "lter", "en")[0].matchReason).toBe("substring");
    expect(searchRecords(records, "Dürer, Albrecht", "en")[0].matchedValue.reason).toBe("approved_alias");
  });

  it("remains complete without Intl.Segmenter and uses a stable explainable tuple", () => {
    Object.defineProperty(Intl, "Segmenter", { configurable: true, value: undefined });
    const records = [
      record("artwork:z-last", "artwork", 1, [preferred("Bathing child")]),
      record("artist:a-first", "artist", 0, [alias("Bathing", "approved_alias")]),
      record("artist:withdrawn", "artist", 0, [preferred("Bathing")], "withdrawn"),
    ];
    const results = searchRecords(records, "Bath", "en");
    expect(results.map((item) => item.record.stable_id)).toEqual(["artist:a-first", "artwork:z-last"]);
    expect(results.every((item) => item.matchReason === "prefix")).toBe(true);
    expect(results.map((item) => item.rankTuple)).toEqual([
      [2, 0, "artist:a-first"],
      [2, 1, "artwork:z-last"],
    ]);
  });

  it("does not synthesize popularity or artistic-value fields", () => {
    const result = searchRecords([record("artist:a", "artist", 0, [preferred("A")])], "A", "en")[0];
    expect(Object.keys(result)).toEqual(["record", "matchReason", "matchedValue", "rankTuple"]);
    expect(result.rankTuple).toEqual([0, 0, "artist:a"]);
  });
});
