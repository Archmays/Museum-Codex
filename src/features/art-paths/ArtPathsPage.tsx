import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useI18n } from "../../i18n/I18nProvider";
import { usePreferences } from "../../preferences/PreferencesProvider";
import { localize, type RelationshipDetails } from "../art-constellation/types";
import { PrintShareControls } from "../art-gallery/observation/PrintShareControls";
import { defaultPathQuery, findPathways } from "./path-algorithm";
import { loadPathwayBundle, PathLoadError } from "./path-loader";
import { PathGraphView } from "./PathGraphView";
import type { ArtistPath, PathMode, PathQuery, PathResult, PathStatus, PathwayBundle } from "./types";
import "./art-paths.css";

type View = "graph" | "text" | "print";
type FormState = { from: string; to: string; mode: PathMode; types: string[]; period: string; region: string; maxHops: number };

const MODE_LEVELS = { historical: ["A", "B"], context: ["B"], comparison: ["C"] } as const;
const URL_KEYS = ["from", "to", "mode", "types", "period", "region", "maxHops", "path", "view"] as const;

const COPY = {
  "zh-CN": {
    eyebrow: "可解释关系导航",
    title: "从 A 到 B，经过哪些可解释关系？",
    intro: "选择两位正式艺术家，在当前公开数据中查找最短 hop 与最多两条替代路径。每一步都可回到 Claim、Evidence 与 Source。",
    from: "起点艺术家", to: "终点艺术家", search: "按中文、英文或别名筛选", swap: "交换端点", mode: "路径模式",
    historical: "历史路径", historicalHelp: "只允许 A 级直接关系与 B 级历史语境关系，并遵守方向。",
    context: "语境路径", contextHelp: "只允许 B 级具体地点、机构、展览、群体或赞助人语境。",
    comparison: "比较路径", comparisonHelp: "只允许 C 级策展比较；必须由你显式选择。",
    filters: "过滤器", type: "关系类型", allTypes: "全部可用类型", period: "时期", region: "地区", any: "不限", maxHops: "最大 hops", run: "查找路径",
    result: "路径结果", alternatives: "替代路径", text: "文字视图", graph: "图形视图", path: "路径", hops: "hops", confidence: "证据置信度",
    coherence: "时间语境", algorithm: "方法", algorithmValue: "有界最短与替代路径", release: "公开版本", filtersApplied: "当前过滤", step: "步骤", direction: "方向", undirected: "无向", directed: "有向：按箭头前进",
    why: "为什么相连", notProve: "不证明什么", contextLabel: "语境", artworks: "支持作品", claim: "Claim", evidence: "Evidence", source: "Source", rights: "权利与署名", withdrawal: "撤回状态", active: "active",
    loading: "正在核验 release 与路径索引……", loadFailed: "路径 release 暂时无法载入。", retry: "重试", invalid: "请修正端点或参数后重新查询。",
    lowBandwidth: "低带宽或 WebGL 不可用：已使用文字视图。", noHistory: "选择只写入可分享 URL；不上传、不保存查询历史，也不运行分析追踪。",
    shortestNotice: "最短路径不等于最真实或最重要；它只回答当前公开数据中可解释的连接。",
    rankNotice: "排序使用确定性 tuple，不合成影响力分数。",
  },
  en: {
    eyebrow: "Explainable relationship navigation",
    title: "What explainable relations connect A to B?",
    intro: "Choose two formal artists and find the shortest hops plus up to two alternatives in the current published data. Every step resolves to Claim, Evidence, and Source.",
    from: "Start artist", to: "End artist", search: "Filter by Chinese, English, or alias", swap: "Swap endpoints", mode: "Path mode",
    historical: "Historical path", historicalHelp: "Allows only direct A relations and historical-context B relations, respecting direction.",
    context: "Context path", contextHelp: "Allows only B relations through specific places, institutions, exhibitions, groups, or patrons.",
    comparison: "Comparison path", comparisonHelp: "Allows only C curatorial comparisons and requires your explicit selection.",
    filters: "Filters", type: "Relationship type", allTypes: "All available types", period: "Period", region: "Region", any: "Any", maxHops: "Maximum hops", run: "Find paths",
    result: "Path results", alternatives: "Alternative paths", text: "Text view", graph: "Graph view", path: "Path", hops: "hops", confidence: "Evidence confidence",
    coherence: "Time context", algorithm: "Method", algorithmValue: "Bounded shortest and alternative paths", release: "Published version", filtersApplied: "Applied filters", step: "Step", direction: "Direction", undirected: "Undirected", directed: "Directed: follow arrow",
    why: "Why connected", notProve: "What this does not prove", contextLabel: "Context", artworks: "Supporting works", claim: "Claim", evidence: "Evidence", source: "Source", rights: "Rights and attribution", withdrawal: "Withdrawal status", active: "active",
    loading: "Verifying the release and path index…", loadFailed: "The pathway release could not be loaded.", retry: "Retry", invalid: "Correct the endpoints or parameters and run the query again.",
    lowBandwidth: "Low bandwidth or unavailable WebGL: text view is active.", noHistory: "Selections are written only to the shareable URL; no query history is uploaded or stored and no analytics run.",
    shortestNotice: "The shortest path is not the truest or most important; it answers only explainable connections in current published data.",
    rankNotice: "Ranking uses a deterministic tuple, not a composite influence score.",
  },
} as const;

function hasWebGl() {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

function normalized(value: string) {
  return value.normalize("NFKD").toLocaleLowerCase().replace(/[\s\p{P}\p{S}]+/gu, "");
}

function formFromParams(params: URLSearchParams, bundle: PathwayBundle): FormState {
  const artistIds = bundle.graph.artists.map((artist) => artist.id);
  const mode = params.get("mode");
  const rawHops = Number(params.get("maxHops"));
  return {
    from: params.get("from") ?? artistIds[0],
    to: params.get("to") ?? artistIds[1],
    mode: mode === "historical" || mode === "context" || mode === "comparison" ? mode : "comparison",
    types: (params.get("types") ?? "").split(",").filter(Boolean),
    period: params.get("period") ?? "",
    region: params.get("region") ?? "",
    maxHops: Number.isInteger(rawHops) && rawHops >= 1 && rawHops <= 6 ? rawHops : 6,
  };
}

function queryFromForm(form: FormState): PathQuery {
  const query = defaultPathQuery(form.from, form.to, form.mode);
  return {
    ...query,
    allowed_relationship_types: form.types,
    allowed_levels: [...MODE_LEVELS[form.mode]],
    period_filter: form.period ? [form.period] : null,
    region_filter: form.region ? [form.region] : null,
    max_hops: form.maxHops,
  };
}

function defaultFilters(form: FormState) {
  return form.types.length === 0 && !form.period && !form.region && form.maxHops === 6;
}

function reverseResult(result: PathResult, query: PathQuery): PathResult {
  return {
    ...result,
    id: `path-result:${query.start_artist_id.replace(":", "-")}--${query.end_artist_id.replace(":", "-")}--${query.mode}`,
    query,
    paths: result.paths.map((path) => ({
      ...path,
      artist_ids: [...path.artist_ids].reverse(),
      relationship_ids: [...path.relationship_ids].reverse(),
      steps: [...path.steps].reverse().map((step, index) => ({
        ...step,
        sequence: index + 1,
        source_artist_id: step.target_artist_id,
        target_artist_id: step.source_artist_id,
      })),
      ranking_tuple: { ...path.ranking_tuple, stable_artist_id_sequence: [...path.artist_ids].reverse(), stable_relation_id_sequence: [...path.relationship_ids].reverse() },
    })),
  };
}

function queryBundle(bundle: PathwayBundle, form: FormState): PathResult {
  const query = queryFromForm(form);
  if (!defaultFilters(form)) return findPathways(bundle.graph, query);
  const pair = bundle.index.pairs.find((candidate) =>
    (candidate.start_artist_id === form.from && candidate.end_artist_id === form.to) ||
    (candidate.start_artist_id === form.to && candidate.end_artist_id === form.from)
  );
  if (!pair) return findPathways(bundle.graph, query);
  const result = pair.modes[form.mode];
  return pair.start_artist_id === form.from ? { ...result, query } : reverseResult(result, query);
}

function statusText(status: PathStatus, locale: "zh-CN" | "en") {
  const text: Record<PathStatus, readonly [string, string]> = {
    ready: ["路径已就绪。", "Paths are ready."],
    no_path_for_current_release_and_filters: ["当前 release 和筛选条件下没有可展示路径，不代表现实中不存在关系。", "No displayable path exists in the current release under these filters; this does not mean no relationship exists in reality."],
    search_budget_reached: ["搜索已达到 10,000 次候选扩展预算；这不是“无路径”结论。", "The search reached its 10,000-candidate expansion budget; this is not a no-path conclusion."],
    invalid_start: ["起点 ID 不属于当前正式艺术家集合。", "The start ID is not in the current formal artist set."],
    invalid_end: ["终点 ID 不属于当前正式艺术家集合。", "The end ID is not in the current formal artist set."],
    same_endpoint: ["起点与终点必须不同。", "Start and end must differ."],
    withdrawn_endpoint: ["所选端点已撤回，不能参与路径。", "A selected endpoint is withdrawn and cannot be used."],
    withdrawn_relation: ["路径包含已撤回关系，结果已阻断。", "The path contains a withdrawn relation and is blocked."],
    incompatible_release: ["URL 或数据所指 release 与当前版本不兼容。", "The URL or data targets an incompatible release."],
    tampered_path_index: ["路径索引 hash 或引用闭包不匹配，已 fail closed。", "The path-index hash or reference closure does not match; loading failed closed."],
    runtime_calculation_failed: ["客户端路径计算失败，请重试。", "Client-side path calculation failed; try again."],
  };
  return text[status][locale === "zh-CN" ? 0 : 1];
}

function AppState({ status, onRetry }: { status: "loading" | PathStatus; onRetry: () => void }) {
  const { locale } = useI18n();
  const copy = COPY[locale];
  const loading = status === "loading";
  return (
    <main id="main-content" className="path-page path-route-state" tabIndex={-1}>
      <p className="eyebrow">{copy.eyebrow}</p>
      <h1>{loading ? copy.loading : copy.loadFailed}</h1>
      {!loading ? <><p role="alert">{statusText(status, locale)}</p><button type="button" onClick={onRetry}>{copy.retry}</button></> : <span className="path-loading-mark" aria-hidden="true" />}
    </main>
  );
}

export default function ArtPathsPage() {
  const [params, setParams] = useSearchParams();
  const [loadKey, setLoadKey] = useState(0);
  const [bundle, setBundle] = useState<PathwayBundle | null>(null);
  const [loadStatus, setLoadStatus] = useState<"loading" | PathStatus>("loading");

  useEffect(() => {
    let current = true;
    loadPathwayBundle().then((loaded) => {
      if (!current) return;
      setBundle(loaded);
      setLoadStatus("ready");
    }).catch((error) => {
      if (!current) return;
      setLoadStatus(error instanceof PathLoadError ? error.status : "runtime_calculation_failed");
    });
    return () => { current = false; };
  }, [loadKey]);

  const retry = () => {
    setLoadStatus("loading");
    setBundle(null);
    setLoadKey((value) => value + 1);
  };
  if (loadStatus === "loading" || !bundle) return <AppState status={loadStatus} onRetry={retry} />;
  return <LoadedPathPage key={params.toString()} bundle={bundle} params={params} setParams={setParams} />;
}

function LoadedPathPage({ bundle, params, setParams }: {
  bundle: PathwayBundle;
  params: URLSearchParams;
  setParams: ReturnType<typeof useSearchParams>[1];
}) {
  const { locale } = useI18n();
  const copy = COPY[locale];
  const { lowBandwidth, forcedColors } = usePreferences();
  const submittedForm = formFromParams(params, bundle);
  const [form, setForm] = useState<FormState>(submittedForm);
  const [search, setSearch] = useState({ from: "", to: "" });
  const [details, setDetails] = useState<Record<string, RelationshipDetails>>({});
  const resultHeading = useRef<HTMLHeadingElement>(null);
  const [webGl] = useState(() => hasWebGl());
  const result = queryBundle(bundle, submittedForm);

  const selectedPath = result?.paths[Math.max(0, Math.min(result.paths.length - 1, Number(params.get("path") ?? "1") - 1))] ?? null;
  const selectedPathKey = selectedPath ? `${selectedPath.id}\u0000${selectedPath.relationship_ids.join("\u0000")}` : "";
  useEffect(() => {
    if (!selectedPathKey) return;
    const [, ...relationshipIds] = selectedPathKey.split("\u0000");
    let current = true;
    void Promise.all(relationshipIds.map((id) => bundle.dataSource.loadRelationshipDetails(id))).then((loaded) => {
      if (!current) return;
      const next: Record<string, RelationshipDetails> = {};
      loaded.forEach((item, index) => { if (item.status === "loaded") next[relationshipIds[index]] = item.data; });
      setDetails(next);
    }, () => undefined);
    return () => { current = false; };
  }, [bundle.dataSource, selectedPathKey]);

  const artistById = new Map(bundle.graph.artists.map((artist) => [artist.id, artist]));
  const periods = [...new Set(bundle.graph.artists.flatMap((artist) => artist.periods))].sort();
  const regions = [...new Set(bundle.graph.artists.flatMap((artist) => artist.regions))].sort();
  const types = [...new Set(bundle.graph.relationships.map((edge) => edge.type))].sort();
  const requestedView = params.get("view");
  const printMode = requestedView === "print";
  const view: View = printMode ? "print" : lowBandwidth || forcedColors || !webGl ? "text" : requestedView === "text" ? "text" : "graph";
  const filteredArtists = (endpoint: "from" | "to") => {
    const key = normalized(search[endpoint]);
    if (!key) return bundle.graph.artists;
    return bundle.graph.artists.filter((artist) => [
      artist.labels["zh-Hans"], artist.labels.en, ...artist.aliases.map((alias) => alias.text),
    ].some((value) => normalized(value).includes(key)));
  };
  const writeParams = (nextForm: FormState, path = 1, nextView = view) => {
    const next = new URLSearchParams();
    next.set("from", nextForm.from);
    next.set("to", nextForm.to);
    next.set("mode", nextForm.mode);
    if (nextForm.types.length) next.set("types", nextForm.types.join(","));
    if (nextForm.period) next.set("period", nextForm.period);
    if (nextForm.region) next.set("region", nextForm.region);
    next.set("maxHops", String(nextForm.maxHops));
    next.set("path", String(path));
    next.set("view", nextView === "print" ? "print" : nextView);
    setParams(next, { replace: true });
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    writeParams(form);
    requestAnimationFrame(() => resultHeading.current?.focus());
  };
  const label = (id: string) => artistById.get(id) ? localize(artistById.get(id)!.labels, locale) : id;
  const draftFilterSummary = [form.types.join(", ") || copy.allTypes, form.period || copy.any, form.region || copy.any, `≤ ${form.maxHops} hops`].join(" · ");
  const filterSummary = [submittedForm.types.join(", ") || copy.allTypes, submittedForm.period || copy.any, submittedForm.region || copy.any, `≤ ${submittedForm.maxHops} hops`].join(" · ");

  return (
    <main id="main-content" className={`path-page${printMode ? " is-print-view" : ""}`} tabIndex={-1}>
      <nav className="path-breadcrumbs" aria-label={locale === "zh-CN" ? "面包屑" : "Breadcrumbs"}>
        <Link to="/art">{locale === "zh-CN" ? "艺术序厅" : "Art foyer"}</Link>
        <Link to="/art/constellation">{locale === "zh-CN" ? "艺术家关系探索" : "Explore Artist Connections"}</Link>
        <Link to="/art/map">{locale === "zh-CN" ? "艺术时空地图" : "Art Across Time and Place"}</Link>
      </nav>
      <header className="path-hero">
        <div><p className="eyebrow">{copy.eyebrow}</p><h1>{copy.title}</h1><p>{copy.intro}</p></div>
        <dl className="path-release-stamp">
          <div><dt>{copy.release}</dt><dd>{bundle.release.version}</dd></div>
          <div><dt>{copy.algorithm}</dt><dd>{copy.algorithmValue}</dd></div>
          <div><dt>Graph</dt><dd>{bundle.graph.artists.length} artists · {bundle.graph.relationships.length} edges</dd></div>
        </dl>
      </header>

      <form className="path-query" onSubmit={submit}>
        <section className="path-endpoints" aria-label={locale === "zh-CN" ? "端点选择" : "Endpoint selection"}>
          {(["from", "to"] as const).map((endpoint) => (
            <div className="path-endpoint" key={endpoint}>
              <label htmlFor={`path-${endpoint}-search`}>{endpoint === "from" ? copy.from : copy.to}</label>
              <input id={`path-${endpoint}-search`} type="search" value={search[endpoint]} placeholder={copy.search} onChange={(event) => setSearch((value) => ({ ...value, [endpoint]: event.target.value }))} />
              <select id={`path-${endpoint}`} aria-label={`${endpoint === "from" ? copy.from : copy.to} · ${locale === "zh-CN" ? "正式艺术家" : "Formal artist"}`} value={form[endpoint]} onChange={(event) => setForm({ ...form, [endpoint]: event.target.value })}>
                {!filteredArtists(endpoint).some((artist) => artist.id === form[endpoint]) ? <option value={form[endpoint]}>{label(form[endpoint])}</option> : null}
                {filteredArtists(endpoint).map((artist) => <option key={artist.id} value={artist.id}>{localize(artist.labels, locale)} · {artist.labels.en}</option>)}
              </select>
            </div>
          ))}
          <button className="path-swap" type="button" onClick={() => setForm({ ...form, from: form.to, to: form.from })} aria-label={copy.swap}>⇄ <span>{copy.swap}</span></button>
        </section>

        <fieldset className="path-modes">
          <legend>{copy.mode}</legend>
          {(["historical", "context", "comparison"] as const).map((mode, index) => (
            <label key={mode} className={form.mode === mode ? "is-selected" : ""}>
              <input type="radio" name="mode" value={mode} checked={form.mode === mode} onChange={() => setForm({ ...form, mode, types: [] })} />
              <span aria-hidden="true">0{index + 1}</span><strong>{copy[mode]}</strong><small>{copy[`${mode}Help`]}</small>
            </label>
          ))}
        </fieldset>

        <details className="path-filters">
          <summary>{copy.filters} · {draftFilterSummary}</summary>
          <div>
            <fieldset><legend>{copy.type}</legend>{types.map((type) => <label key={type}><input type="checkbox" checked={form.types.includes(type)} onChange={(event) => setForm({ ...form, types: event.target.checked ? [...form.types, type].sort() : form.types.filter((value) => value !== type) })} />{type.replaceAll("_", " ")}</label>)}</fieldset>
            <label>{copy.period}<select value={form.period} onChange={(event) => setForm({ ...form, period: event.target.value })}><option value="">{copy.any}</option>{periods.map((period) => <option key={period}>{period}</option>)}</select></label>
            <label>{copy.region}<select value={form.region} onChange={(event) => setForm({ ...form, region: event.target.value })}><option value="">{copy.any}</option>{regions.map((region) => <option key={region}>{region}</option>)}</select></label>
            <label>{copy.maxHops}<select value={form.maxHops} onChange={(event) => setForm({ ...form, maxHops: Number(event.target.value) })}>{[1, 2, 3, 4, 5, 6].map((value) => <option key={value}>{value}</option>)}</select></label>
          </div>
        </details>
        <div className="path-query-submit"><button type="submit">{copy.run}<span aria-hidden="true"> →</span></button><p>{copy.noHistory}</p></div>
      </form>

      <section className="path-results" aria-labelledby="path-results-title">
        <header className="path-results-header">
          <div><p className="eyebrow">{copy.result}</p><h2 id="path-results-title" tabIndex={-1} ref={resultHeading}>{label(submittedForm.from)} <span aria-hidden="true">→</span> {label(submittedForm.to)}</h2></div>
          <div className="path-view-tabs" role="group" aria-label={locale === "zh-CN" ? "结果视图" : "Result view"}>
            <button type="button" aria-pressed={view === "graph"} disabled={lowBandwidth || forcedColors || !webGl} onClick={() => writeParams(submittedForm, Number(params.get("path") ?? 1), "graph")}>{copy.graph}</button>
            <button type="button" aria-pressed={view !== "graph"} onClick={() => writeParams(submittedForm, Number(params.get("path") ?? 1), "text")}>{copy.text}</button>
          </div>
        </header>
        {(lowBandwidth || forcedColors || !webGl) && !printMode ? <p className="path-fallback-note">{copy.lowBandwidth}</p> : null}
        <p className={`path-status is-${result.status}`} role="status" aria-live="polite" aria-atomic="true">{statusText(result.status, locale)}</p>
        {result.paths.length ? (
          <>
            <div className="path-alternatives" role="tablist" aria-label={copy.alternatives}>
              {result.paths.map((path, index) => <button key={path.id} type="button" role="tab" aria-selected={selectedPath?.id === path.id} onClick={() => writeParams(submittedForm, index + 1)}>{copy.path} {index + 1}<small>{path.hop_count} {copy.hops}</small></button>)}
            </div>
            {selectedPath ? <PathResultView path={selectedPath} bundle={bundle} details={details} locale={locale} view={view} copy={copy} label={label} filterSummary={filterSummary} /> : null}
          </>
        ) : <div className="path-empty"><span aria-hidden="true">∅</span><p>{result.status === "search_budget_reached" ? statusText("search_budget_reached", locale) : statusText(result.status, locale)}</p></div>}
      </section>

      <aside className="path-method-notice"><p><strong>{copy.shortestNotice}</strong></p><p>{copy.rankNotice}</p><p>{localize(result.disclaimer, locale)}</p></aside>
      <PrintShareControls releaseId={bundle.release.manifestId} releaseVersion={bundle.release.version} state={Object.fromEntries(URL_KEYS.map((key) => [key, params.get(key)]))} />
    </main>
  );
}

function PathResultView({ path, bundle, details, locale, view, copy, label, filterSummary }: {
  path: ArtistPath;
  bundle: PathwayBundle;
  details: Record<string, RelationshipDetails>;
  locale: "zh-CN" | "en";
  view: View;
  copy: typeof COPY["zh-CN"] | typeof COPY.en;
  label: (id: string) => string;
  filterSummary: string;
}) {
  return (
    <article className="path-result-card" aria-labelledby={`path-title-${path.rank}`}>
      <header>
        <div><p className="path-rank">{copy.path} {path.rank}</p><h3 id={`path-title-${path.rank}`}>{path.artist_ids.map(label).join(" → ")}</h3></div>
        <dl>
          <div><dt>{copy.hops}</dt><dd>{path.hop_count}</dd></div>
          <div><dt>{copy.confidence}</dt><dd>{Math.round(path.evidence_confidence * 100)}%</dd></div>
          <div><dt>{copy.coherence}</dt><dd>{path.time_coherence}</dd></div>
          <div><dt>Level</dt><dd>{path.evidence_level}｜{path.evidence_level === "C" ? (locale === "zh-CN" ? "策展比较" : "Curatorial comparison") : path.evidence_level}</dd></div>
        </dl>
        <p>{copy.algorithm}: {copy.algorithmValue} · {copy.filtersApplied}: {filterSummary} · {copy.release}: {bundle.release.version}</p>
      </header>
      {view === "graph" ? <PathGraphView artists={bundle.graph.artists} relationships={bundle.graph.relationships} path={path} locale={locale} /> : null}
      <section className="path-text-equivalent" aria-labelledby={`path-steps-${path.rank}`}>
        <h4 id={`path-steps-${path.rank}`}>{locale === "zh-CN" ? "按顺序阅读路径" : "Read the path in order"}</h4>
        <ol>
          {path.steps.map((step) => {
            const detail = details[step.relationship_id];
            return (
              <li key={step.relationship_id}>
                <article>
                  <header><span>{String(step.sequence).padStart(2, "0")}</span><div><p>{step.level}｜{step.level === "C" ? (locale === "zh-CN" ? "策展比较" : "Curatorial comparison") : step.relationship_type}</p><h5>{label(step.source_artist_id)} <span aria-hidden="true">{step.direction === "undirected" ? "↔" : "→"}</span> {label(step.target_artist_id)}</h5></div></header>
                  <dl className="path-step-facts">
                    <div><dt>{copy.direction}</dt><dd>{step.direction === "undirected" ? copy.undirected : copy.directed}</dd></div>
                    <div><dt>Type</dt><dd>{step.relationship_type.replaceAll("_", " ")}</dd></div>
                    <div><dt>{copy.confidence}</dt><dd>{Math.round(step.evidence_confidence * 100)}%</dd></div>
                    <div><dt>{copy.withdrawal}</dt><dd>{copy.active}</dd></div>
                  </dl>
                  <div className="path-step-meaning"><section><h6>{copy.why}</h6><p>{localize(step.why_connected, locale)}</p></section><section><h6>{copy.notProve}</h6><p>{localize(step.does_not_prove, locale)}</p></section></div>
                  <details>
                    <summary>{copy.claim} → {copy.evidence} → {copy.source}</summary>
                    <div className="path-closure-grid">
                      <section><h6>{copy.claim}</h6><ul>{step.claim_ids.map((id) => <li key={id}><code>{id}</code></li>)}</ul></section>
                      <section><h6>{copy.evidence}</h6>{detail ? <ul>{detail.evidence.map((item) => <li key={item.id}><code>{item.id}</code><p>{localize(item.summary, locale)}</p></li>)}</ul> : <p>{locale === "zh-CN" ? "正在载入证据说明……" : "Loading evidence descriptions…"}</p>}</section>
                      <section><h6>{copy.source}</h6>{detail ? <ul>{detail.sources.map((source) => <li key={source.id}><a href={source.officialUrl}>{source.title}</a><p>{source.publisher} · {source.license}</p></li>)}</ul> : <p>{locale === "zh-CN" ? "正在载入来源……" : "Loading sources…"}</p>}</section>
                    </div>
                  </details>
                  <details><summary>{copy.contextLabel} · {copy.artworks} · {copy.rights}</summary><div className="path-support-grid"><section><h6>{copy.contextLabel}</h6><p>{detail?.contexts.map((item) => localize(item.labels, locale)).join(" · ") || step.context_ids.join(" · ")}</p></section><section><h6>{copy.artworks}</h6><ul>{detail?.artworks.map((artwork) => <li key={artwork.id}><Link to={`/art/artworks/${encodeURIComponent(artwork.id)}`}>{localize(artwork.title, locale)}</Link></li>) ?? step.supporting_artwork_ids.map((id) => <li key={id}><code>{id}</code></li>)}</ul></section><section><h6>{copy.rights}</h6><p>{step.rights_attribution.join(" · ")}</p></section></div></details>
                </article>
              </li>
            );
          })}
        </ol>
      </section>
    </article>
  );
}
