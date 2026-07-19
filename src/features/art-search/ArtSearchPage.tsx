import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useI18n } from "../../i18n/I18nProvider";
import { loadSearchIndex, type SearchIndexHandle } from "./search-loader";
import { searchRecords } from "./search-model";
import type { MatchReason, SearchRecord, SearchResult } from "./types";
import "./art-search.css";

const ENTITY_LABELS = {
  artist: ["艺术家", "Artist"],
  artwork: ["作品", "Artwork"],
  context: ["语境", "Context"],
  tour: ["导览", "Tour"],
  place: ["地点", "Place"],
  relationship: ["关系解释", "Relationship"],
  path: ["关系路径", "Path"],
  page: ["帮助页面", "Help page"],
} as const;

const REASON_LABELS: Record<MatchReason, readonly [string, string]> = {
  exact_preferred: ["首选名称完全匹配", "Exact preferred label"],
  exact_alias: ["别名、转写或原语言名称完全匹配", "Exact alias, transliteration, or source-language label"],
  prefix: ["名称前缀匹配", "Prefix match"],
  segmenter_token: ["浏览器分词 token 匹配", "Browser token match"],
  substring: ["名称或说明包含匹配", "Substring match"],
};

function textFor(record: SearchRecord, field: "labels" | "description", locale: "zh-CN" | "en") {
  const values = record[field];
  return values[locale === "zh-CN" ? "zh-Hans" : "en"] ?? values.en ?? values["zh-Hans"] ?? Object.values(values)[0] ?? record.stable_id;
}

function resultLink(result: SearchResult) {
  return result.record.route;
}

export default function ArtSearchPage() {
  const { locale } = useI18n();
  const [params, setParams] = useSearchParams();
  const query = params.get("q")?.slice(0, 160) ?? "";
  const requestedType = params.get("type") ?? "";
  const [draftState, setDraftState] = useState({ sourceQuery: query, value: query });
  const draft = draftState.sourceQuery === query ? draftState.value : query;
  const [handle, setHandle] = useState<SearchIndexHandle | null>(null);
  const [records, setRecords] = useState<SearchRecord[]>([]);
  const [loadState, setLoadState] = useState<"loading" | "ready" | "failed">("loading");
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    let active = true;
    loadSearchIndex().then((value) => {
      if (!active) return;
      setHandle(value);
      setLoadState("ready");
    }).catch(() => {
      if (active) setLoadState("failed");
    });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!query || !handle || records.length > 0) return;
    let active = true;
    handle.loadRecords().then((value) => {
      if (!active) return;
      setRecords(value);
      requestAnimationFrame(() => headingRef.current?.focus());
    }).catch(() => {
      if (active) setLoadState("failed");
    });
    return () => { active = false; };
  }, [handle, query, records.length]);

  const status: "loading" | "ready" | "querying" | "failed" =
    loadState === "failed"
      ? "failed"
      : !handle
        ? "loading"
        : query && records.length === 0
          ? "querying"
          : "ready";

  const allResults = useMemo(() => searchRecords(records, query, locale), [records, query, locale]);
  const results = requestedType
    ? allResults.filter((result) => result.record.entity_type === requestedType)
    : allResults;
  const entityTypes = handle ? Object.keys(handle.manifest.counts.by_entity_type).sort() : [];

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const next = new URLSearchParams();
    const cleanQuery = draft.trim().slice(0, 160);
    if (cleanQuery) next.set("q", cleanQuery);
    if (requestedType) next.set("type", requestedType);
    setParams(next, { replace: true });
  };
  const setType = (type: string) => {
    const next = new URLSearchParams(params);
    if (type) next.set("type", type);
    else next.delete("type");
    setParams(next, { replace: true });
  };
  const retry = () => {
    setHandle(null);
    setRecords([]);
    setLoadState("loading");
    void loadSearchIndex().then((value) => {
      setHandle(value);
      setLoadState("ready");
    }).catch(() => setLoadState("failed"));
  };

  return (
    <main id="main-content" className="art-search-page" tabIndex={-1}>
      <nav className="search-breadcrumbs" aria-label={locale === "zh-CN" ? "面包屑" : "Breadcrumbs"}>
        <Link to="/art">{locale === "zh-CN" ? "艺术序厅" : "Art foyer"}</Link>
        <Link to="/art/artists">{locale === "zh-CN" ? "艺术家" : "Artists"}</Link>
        <Link to="/rights">{locale === "zh-CN" ? "权利与来源" : "Rights and sources"}</Link>
      </nav>
      <header className="search-hero">
        <p className="eyebrow">{locale === "zh-CN" ? "本地、可解释、无记录" : "Local, explainable, and unlogged"}</p>
        <h1>{locale === "zh-CN" ? "搜索美术馆" : "Search the art museum"}</h1>
        <p>{locale === "zh-CN" ? "搜索公开的艺术家、作品、语境、导览、地点、关系与路径。排序只使用匹配类型、访客任务实体类型与稳定 ID。" : "Search public artists, artworks, contexts, tours, places, relationships, and paths. Ranking uses only match class, visitor-task entity type, and stable ID."}</p>
      </header>

      <form className="search-form" role="search" onSubmit={submit}>
        <label htmlFor="museum-search-query">{locale === "zh-CN" ? "中文、英文、别名、转写或原语言名称" : "Chinese, English, alias, transliteration, or source-language label"}</label>
        <div>
          <input
            id="museum-search-query"
            type="search"
            autoComplete="off"
            spellCheck={false}
            value={draft}
            maxLength={160}
            onChange={(event) => setDraftState({ sourceQuery: query, value: event.target.value })}
          />
          <button type="submit">{locale === "zh-CN" ? "搜索" : "Search"}</button>
        </div>
        <p>{locale === "zh-CN" ? "搜索词不会写入本地存储、Cookie 或远程日志；当前 URL 只用于你主动分享。" : "Queries are not written to local storage, cookies, or remote logs; the current URL exists only for sharing you initiate."}</p>
      </form>

      {query && handle ? (
        <section className="search-results" aria-labelledby="search-results-title" aria-busy={status === "querying"}>
          <header>
            <div>
              <p className="eyebrow">{locale === "zh-CN" ? "结果" : "Results"}</p>
              <h2 id="search-results-title" ref={headingRef} tabIndex={-1}>
                {status === "querying"
                  ? (locale === "zh-CN" ? "正在载入索引分片……" : "Loading index shards…")
                  : (locale === "zh-CN" ? `${results.length} 条匹配` : `${results.length} matches`)}
              </h2>
            </div>
            <label>{locale === "zh-CN" ? "实体类型" : "Entity type"}
              <select value={requestedType} onChange={(event) => setType(event.target.value)}>
                <option value="">{locale === "zh-CN" ? "全部" : "All"}</option>
                {entityTypes.map((type) => <option key={type} value={type}>{ENTITY_LABELS[type as keyof typeof ENTITY_LABELS]?.[locale === "zh-CN" ? 0 : 1] ?? type}</option>)}
              </select>
            </label>
          </header>
          <p className="sr-only" role="status" aria-live="polite">
            {status === "querying" ? (locale === "zh-CN" ? "正在搜索" : "Searching") : `${results.length}`}
          </p>
          {status !== "querying" && results.length === 0 ? (
            <div className="search-empty">
              <h3>{locale === "zh-CN" ? "当前公开索引没有匹配" : "No match in the current public index"}</h3>
              <p>{locale === "zh-CN" ? "尝试更短的名称、别名或原语言拼写。没有结果不表示现实中不存在相关对象。" : "Try a shorter name, alias, or source-language spelling. No result does not mean the object does not exist in reality."}</p>
            </div>
          ) : (
            <ol>
              {results.map((result) => (
                <li key={result.record.id}>
                  <article>
                    <div>
                      <span>{ENTITY_LABELS[result.record.entity_type][locale === "zh-CN" ? 0 : 1]}</span>
                      <small>{REASON_LABELS[result.matchReason][locale === "zh-CN" ? 0 : 1]}</small>
                    </div>
                    <h3><Link to={resultLink(result)}>{textFor(result.record, "labels", locale)}</Link></h3>
                    <p>{textFor(result.record, "description", locale)}</p>
                    <p className="search-match-detail">
                      {locale === "zh-CN" ? "匹配文本" : "Matched text"}: <q>{result.matchedValue.text}</q>
                      <code>{result.record.stable_id}</code>
                    </p>
                  </article>
                </li>
              ))}
            </ol>
          )}
        </section>
      ) : (
        <section className="search-start" aria-labelledby="search-start-title">
          <h2 id="search-start-title">{locale === "zh-CN" ? "索引在首次搜索时按需载入" : "Index shards load on the first search"}</h2>
          <p>{locale === "zh-CN" ? "初始页面不加载作品媒体，不发出外部请求；浏览器不支持 Intl.Segmenter 时，Unicode normalization、完全匹配、前缀、子串、别名与转写仍可完成搜索。" : "The initial page loads no artwork media and makes no external request. Without Intl.Segmenter, Unicode normalization, exact, prefix, substring, alias, and transliteration matching remain complete."}</p>
        </section>
      )}

      {status === "failed" ? (
        <section className="search-error" role="alert">
          <h2>{locale === "zh-CN" ? "搜索资料暂不可用" : "Search material is unavailable"}</h2>
          <p>{locale === "zh-CN" ? "当前静态索引未通过完整性核验；其他美术馆路由仍可使用。" : "The static index did not pass integrity checks; other museum routes remain available."}</p>
          <button type="button" onClick={retry}>{locale === "zh-CN" ? "重试" : "Retry"}</button>
        </section>
      ) : null}
    </main>
  );
}
