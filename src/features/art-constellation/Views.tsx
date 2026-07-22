import { memo, useMemo, useState, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import type { Locale, Translation } from "../../i18n/translations";
import { relationshipTypeLabel } from "./labels";
import type { MatchReason } from "./model";
import {
  CONSTELLATION_LIST_PAGE_SIZE,
  CONSTELLATION_TABLE_PAGE_SIZE,
  planFocusedExplorer,
  stablePage,
} from "./scale-strategy";
import { localize, type ArtistRecord, type ContextRecord, type RelationshipExplorerConfig, type RelationshipRecord, type RelationshipType } from "./types";

type Copy = Translation["constellation"];

type SharedViewProps = {
  artists: ArtistRecord[];
  relationships: RelationshipRecord[];
  locale: Locale;
  copy: Copy;
  focusArtistId: string | null;
  selectedRelationshipId: string | null;
  matchReasons: Map<string, MatchReason>;
  relationshipIndexLoaded: boolean;
  onSelectArtist: (artistId: string, trigger?: HTMLElement) => void;
  onSelectRelationship: (relationshipId: string, trigger?: HTMLElement) => void;
};

function matchReasonLabel(reason: MatchReason | undefined, copy: Copy) {
  if (!reason) return null;
  return {
    exact: copy.matchExact,
    prefix: copy.matchPrefix,
    substring: copy.matchSubstring,
    alias: copy.matchAlias,
  }[reason];
}

function relationshipCount(artist: ArtistRecord, relationships: RelationshipRecord[], relationshipIndexLoaded: boolean) {
  if (!relationshipIndexLoaded) return artist.relationCount;
  return relationships.filter(
    (relationship) => relationship.sourceArtistId === artist.id || relationship.targetArtistId === artist.id,
  ).length;
}

export function EmptyView({ copy }: { copy: Copy }) {
  return (
    <section className="constellation-empty" aria-labelledby="constellation-empty-title">
      <span aria-hidden="true">∅</span>
      <div>
        <h2 id="constellation-empty-title">{copy.noResultsTitle}</h2>
        <p>{copy.noResultsText}</p>
      </div>
    </section>
  );
}

const LANE_LABELS: Record<RelationshipType, { "zh-CN": string; en: string }> = {
  shared_subject: { "zh-CN": "共同题材", en: "Shared subject" },
  shared_material: { "zh-CN": "共同材料", en: "Shared material" },
  shared_technique: { "zh-CN": "共同技法", en: "Shared technique" },
};

function ArtistCard({ artist, locale, onSelect }: { artist: ArtistRecord; locale: Locale; onSelect: (trigger: HTMLElement) => void }) {
  const name = localize(artist.labels, locale);
  return (
    <article className="relation-artist-card" data-artist-id={artist.id}>
      <p>{artist.lifeDisplay ? localize(artist.lifeDisplay, locale) : artist.period}</p>
      <h3>{name}</h3>
      <p>{localize(artist.publicIntro ?? artist.summary, locale)}</p>
      <div className="relation-artist-actions">
        <button type="button" onClick={(event) => onSelect(event.currentTarget)}>
          {locale === "zh-CN" ? "以此人为中心" : "Center this artist"}
        </button>
        <Link to={`/art/artists/${artist.publicSlug}`}>{locale === "zh-CN" ? "进入展厅" : "Visit gallery"}</Link>
      </div>
    </article>
  );
}

function RelationEdge({ relationship, locale, selected, onOpen }: { relationship: RelationshipRecord; locale: Locale; selected: boolean; onOpen: (trigger: HTMLElement) => void }) {
  const title = localize(relationship.title, locale);
  const activate = (event: KeyboardEvent<SVGGElement>) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    onOpen(event.currentTarget as unknown as HTMLElement);
  };
  return (
    <div className={`relation-edge ${relationship.type}${selected ? " is-selected" : ""}`}>
      <svg viewBox="0 0 240 28" role="img" aria-labelledby={`${relationship.id}-title`}>
        <title id={`${relationship.id}-title`}>{title}</title>
        <g role="button" tabIndex={0} aria-label={title} onClick={(event) => onOpen(event.currentTarget as unknown as HTMLElement)} onKeyDown={activate}>
          <path className="relation-edge-hit" d="M4 14 H236" />
          <path className="relation-edge-line" d="M4 14 H236" />
        </g>
      </svg>
      <button type="button" onClick={(event) => onOpen(event.currentTarget)}>
        {locale === "zh-CN" ? "为什么相连？" : "Why connected?"}
      </button>
    </div>
  );
}

export function StartExplorerView({ artists, starterArtistIds, locale, onSelectArtist }: {
  artists: ArtistRecord[];
  starterArtistIds: string[];
  locale: Locale;
  onSelectArtist: (artistId: string, trigger?: HTMLElement) => void;
}) {
  const byId = new Map(artists.map((artist) => [artist.id, artist]));
  const starters = starterArtistIds.map((id) => byId.get(id)).filter((artist): artist is ArtistRecord => Boolean(artist));
  return (
    <section className="relation-start" aria-labelledby="relation-start-title" data-default-node-count="0">
      <div className="relation-start-copy">
        <p className="eyebrow">{locale === "zh-CN" ? "从一个问题开始" : "Begin with a question"}</p>
        <h2 id="relation-start-title">{locale === "zh-CN" ? "你想先认识哪位艺术家？" : "Which artist would you like to meet first?"}</h2>
        <p>{locale === "zh-CN" ? "搜索姓名，或从下列跨时期、地区与实践的示例中选择。这里没有默认全局关系图。" : "Search by name, or choose from these examples across periods, regions, and practices. There is no default global graph."}</p>
      </div>
      <div className="relation-starters">
        {starters.map((artist) => (
          <button key={artist.id} type="button" onClick={(event) => onSelectArtist(artist.id, event.currentTarget)}>
            <span>{artist.region} · {artist.period}</span>
            <strong>{localize(artist.labels, locale)}</strong>
            <small>{localize(artist.mediaPractice, locale)}</small>
          </button>
        ))}
      </div>
    </section>
  );
}

function GraphViewComponent({
  artists,
  relationships,
  locale,
  copy,
  focusArtistId,
  selectedRelationshipId,
  relationshipIndexLoaded,
  explorerConfig,
  expanded,
  onExpandedChange,
  onSelectArtist,
  onSelectRelationship,
}: SharedViewProps & {
  explorerConfig: RelationshipExplorerConfig;
  expanded: boolean;
  onExpandedChange: (expanded: boolean) => void;
}) {
  const plan = useMemo(() => planFocusedExplorer(
    artists,
    relationships,
    focusArtistId,
    locale,
    expanded,
    explorerConfig.focusInitialNeighborLimit,
    explorerConfig.focusInitialPerLaneLimit,
    explorerConfig.focusExpandedNodeLimit,
  ), [artists, expanded, explorerConfig, focusArtistId, locale, relationships]);
  const lanes = explorerConfig.laneOrder.map((lane) => ({ lane, neighbors: plan.neighbors.filter((neighbor) => neighbor.primaryLane === lane) }));
  const focusArtist = plan.focusArtist;
  const allDirect = focusArtist ? artists.filter((artist) => artist.id !== focusArtist.id && relationships.some((relationship) => (
    relationship.sourceArtistId === focusArtist.id && relationship.targetArtistId === artist.id
  ) || (
    relationship.targetArtistId === focusArtist.id && relationship.sourceArtistId === artist.id
  ))) : [];
  if (!plan.focusArtist) return <p className="constellation-graph-loading" role="status">{relationshipIndexLoaded ? copy.graphInitial : copy.relationsLoading}</p>;
  return (
    <section className="focused-relation-explorer" aria-label={copy.graphView} data-node-count={plan.totalNodeCount}>
      <header className="focused-relation-heading">
        <div>
          <p className="eyebrow">{locale === "zh-CN" ? "艺术家关系" : "Artist relationships"}</p>
          <h2>{localize(plan.focusArtist.labels, locale)}</h2>
          <p>{localize(plan.focusArtist.publicIntro ?? plan.focusArtist.summary, locale)}</p>
        </div>
        <nav aria-label={locale === "zh-CN" ? "艺术家任务" : "Artist tasks"}>
          <Link to={`/art/artists/${plan.focusArtist.publicSlug}`}>{locale === "zh-CN" ? "艺术家展厅" : "Artist gallery"}</Link>
          <Link to={`/art/compare?artist=${encodeURIComponent(plan.focusArtist.id)}`}>{locale === "zh-CN" ? "比较作品" : "Compare works"}</Link>
          <Link to={`/art/paths?artist=${encodeURIComponent(plan.focusArtist.id)}`}>{locale === "zh-CN" ? "跟随路径" : "Follow a path"}</Link>
        </nav>
      </header>
      <div className="relation-lanes">
        {lanes.map(({ lane, neighbors }) => (
          <section key={lane} className={`relation-lane ${lane}`} aria-labelledby={`lane-${lane}`}>
            <h3 id={`lane-${lane}`}>{LANE_LABELS[lane][locale]}</h3>
            {neighbors.length ? neighbors.map((neighbor) => {
              const edge = neighbor.relationships.find((relationship) => relationship.type === lane) ?? neighbor.relationships[0];
              return (
                <div className="relation-lane-item" key={neighbor.artist.id}>
                  {edge ? <RelationEdge relationship={edge} locale={locale} selected={edge.id === selectedRelationshipId} onOpen={(trigger) => onSelectRelationship(edge.id, trigger)} /> : null}
                  <ArtistCard artist={neighbor.artist} locale={locale} onSelect={(trigger) => onSelectArtist(neighbor.artist.id, trigger)} />
                </div>
              );
            }) : <p className="relation-lane-empty">{locale === "zh-CN" ? "当前筛选下暂无这一类正式关系。" : "No formal relationship of this type matches the current filters."}</p>}
          </section>
        ))}
      </div>
      <div className="focused-relation-footer">
        {plan.hiddenDirectNeighborCount > 0 ? <button type="button" onClick={() => onExpandedChange(!expanded)}>{expanded ? (locale === "zh-CN" ? "收起" : "Show less") : (locale === "zh-CN" ? `展开更多（还有 ${plan.hiddenDirectNeighborCount} 位）` : `Show more (${plan.hiddenDirectNeighborCount} more)`)}</button> : null}
        <p>{locale === "zh-CN" ? `当前显示 ${plan.totalNodeCount} 个节点；初始不超过 13 个，展开后不超过 20 个。` : `${plan.totalNodeCount} nodes are visible; the initial view has at most 13 and the expanded view at most 20.`}</p>
      </div>
      {allDirect.length > plan.neighbors.length ? (
        <details className="complete-neighbor-list">
          <summary>{locale === "zh-CN" ? `查看完整的一跳文字列表（${allDirect.length}）` : `View the complete one-hop text list (${allDirect.length})`}</summary>
          <ul>{allDirect.map((artist) => <li key={artist.id}><button type="button" onClick={(event) => onSelectArtist(artist.id, event.currentTarget)}>{localize(artist.labels, locale)}</button></li>)}</ul>
        </details>
      ) : null}
      <p className="relation-semantics">{localize(explorerConfig.semantics, locale)}</p>
    </section>
  );
}

export const GraphView = memo(GraphViewComponent);

export function ThemeExplorerView({ artists, relationships, contexts, contextId, locale, config, onSelectArtist, onSelectRelationship }: {
  artists: ArtistRecord[];
  relationships: RelationshipRecord[];
  contexts: ContextRecord[];
  contextId: string;
  locale: Locale;
  config: RelationshipExplorerConfig;
  onSelectArtist: (artistId: string, trigger?: HTMLElement) => void;
  onSelectRelationship: (relationshipId: string, trigger?: HTMLElement) => void;
}) {
  const [requestedPage, setRequestedPage] = useState(1);
  const context = contexts.find((candidate) => candidate.id === contextId);
  const sorted = useMemo(() => [...artists].sort((left, right) => localize(left.labels, locale).localeCompare(localize(right.labels, locale), locale) || left.id.localeCompare(right.id)), [artists, locale]);
  const visual = sorted.slice(0, config.themeVisualArtistLimit);
  const page = stablePage(sorted, requestedPage, config.themeTextPageSize);
  if (!context) return <p role="status">{locale === "zh-CN" ? "请选择一个主题语境。" : "Choose a theme context."}</p>;
  return (
    <section className="theme-explorer" aria-labelledby="theme-explorer-title">
      <header><p className="eyebrow">{locale === "zh-CN" ? "主题模式" : "Theme mode"}</p><h2 id="theme-explorer-title">{localize(context.labels, locale)}</h2><p>{locale === "zh-CN" ? `视觉区最多展示 ${config.themeVisualArtistLimit} 位艺术家；下方文字列表保留全部匹配项。` : `The visual area shows at most ${config.themeVisualArtistLimit} artists; the complete matching set remains in the text list below.`}</p></header>
      <div className="theme-artist-grid">{visual.map((artist) => <ArtistCard key={artist.id} artist={artist} locale={locale} onSelect={(trigger) => onSelectArtist(artist.id, trigger)} />)}</div>
      <details className="theme-relationship-list"><summary>{locale === "zh-CN" ? `查看这一主题的正式关系（${relationships.length}）` : `View formal relationships in this theme (${relationships.length})`}</summary><ul>{relationships.map((relationship) => <li key={relationship.id}><button type="button" onClick={(event) => onSelectRelationship(relationship.id, event.currentTarget)}>{localize(relationship.title, locale)}</button></li>)}</ul></details>
      <nav className="theme-complete-list" aria-label={locale === "zh-CN" ? "主题艺术家完整列表" : "Complete theme artist list"}>
        <ol start={page.start + 1}>{page.items.map((artist) => <li key={artist.id}><button type="button" onClick={(event) => onSelectArtist(artist.id, event.currentTarget)}>{localize(artist.labels, locale)}</button></li>)}</ol>
        {page.pageCount > 1 ? <div className="scale-pagination"><button type="button" disabled={page.page === 1} onClick={() => setRequestedPage(page.page - 1)}>{locale === "zh-CN" ? "上一页" : "Previous"}</button><span>{page.page} / {page.pageCount} · {page.total}</span><button type="button" disabled={page.page === page.pageCount} onClick={() => setRequestedPage(page.page + 1)}>{locale === "zh-CN" ? "下一页" : "Next"}</button></div> : null}
      </nav>
    </section>
  );
}

function ArtistListViewComponent({
  artists,
  relationships,
  locale,
  copy,
  focusArtistId,
  matchReasons,
  relationshipIndexLoaded,
  onSelectArtist,
}: SharedViewProps) {
  const [requestedPage, setRequestedPage] = useState(1);
  const window = stablePage(artists, requestedPage, CONSTELLATION_LIST_PAGE_SIZE);
  return (
    <section className="artist-list-view" aria-label={copy.listView}>
      <ol>
        {window.items.map((artist, index) => {
          const name = localize(artist.labels, locale);
          const reason = matchReasonLabel(matchReasons.get(artist.id), copy);
          const count = relationshipCount(artist, relationships, relationshipIndexLoaded);
          return (
            <li key={artist.id} className={artist.id === focusArtistId ? "is-selected" : undefined}>
              <span className="artist-list-index">{String(window.start + index + 1).padStart(2, "0")}</span>
              <div>
                <p className="artist-list-kicker">{artist.lifeDisplay ? localize(artist.lifeDisplay, locale) : artist.period}</p>
                <h2>{name}</h2>
                <p>{localize(artist.summary, locale)}</p>
                <dl>
                  <div><dt>{copy.periodRegion}</dt><dd>{artist.period} · {artist.region}</dd></div>
                  <div><dt>{copy.relatedRelationships}</dt><dd>{count} C</dd></div>
                </dl>
                {reason ? <p className="match-reason">{reason}</p> : null}
                <button type="button" onClick={(event) => onSelectArtist(artist.id, event.currentTarget)}>
                  {copy.openArtist}
                </button>
              </div>
            </li>
          );
        })}
      </ol>
      {window.pageCount > 1 ? (
        <nav className="scale-pagination" aria-label={locale === "zh-CN" ? "艺术家列表分页" : "Artist list pagination"}>
          <button type="button" disabled={window.page === 1} onClick={() => setRequestedPage(window.page - 1)}>
            {locale === "zh-CN" ? "上一页" : "Previous"}
          </button>
          <span>{window.page} / {window.pageCount} · {window.total}</span>
          <button type="button" disabled={window.page === window.pageCount} onClick={() => setRequestedPage(window.page + 1)}>
            {locale === "zh-CN" ? "下一页" : "Next"}
          </button>
        </nav>
      ) : null}
    </section>
  );
}

export const ArtistListView = memo(ArtistListViewComponent);

type SortKey = "title" | "type" | "confidence";

function RelationshipTableViewComponent({
  artists,
  relationships,
  contexts,
  locale,
  copy,
  onSelectArtist,
  onSelectRelationship,
}: SharedViewProps & { contexts: ContextRecord[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("title");
  const [ascending, setAscending] = useState(true);
  const [requestedPage, setRequestedPage] = useState(1);
  const artistById = useMemo(() => new Map(artists.map((artist) => [artist.id, artist])), [artists]);
  const contextById = useMemo(() => new Map(contexts.map((context) => [context.id, context])), [contexts]);
  const sorted = useMemo(() => {
    return [...relationships].sort((left, right) => {
      const leftValue = sortKey === "confidence" ? left.evidenceConfidence : sortKey === "type" ? left.type : localize(left.title, locale);
      const rightValue = sortKey === "confidence" ? right.evidenceConfidence : sortKey === "type" ? right.type : localize(right.title, locale);
      const order = typeof leftValue === "number" && typeof rightValue === "number"
        ? leftValue - rightValue
        : String(leftValue).localeCompare(String(rightValue), locale);
      return ascending ? order : -order;
    });
  }, [ascending, locale, relationships, sortKey]);
  const window = stablePage(sorted, requestedPage, CONSTELLATION_TABLE_PAGE_SIZE);

  const changeSort = (nextKey: SortKey) => {
    if (nextKey === sortKey) setAscending((current) => !current);
    else {
      setSortKey(nextKey);
      setAscending(true);
    }
  };
  const sortValue = (key: SortKey) => sortKey === key ? (ascending ? "ascending" : "descending") : "none";

  return (
    <section className="relationship-table-view" aria-label={copy.tableView}>
      <div className="relationship-table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col" aria-sort={sortValue("title")}><button type="button" onClick={() => changeSort("title")}>{copy.sortTitle}</button></th>
              <th scope="col">{copy.endpoint}</th>
              <th scope="col" aria-sort={sortValue("type")}><button type="button" onClick={() => changeSort("type")}>{copy.sortType}</button></th>
              <th scope="col">{copy.level}</th>
              <th scope="col">{copy.sharedContext}</th>
              <th scope="col" aria-sort={sortValue("confidence")}><button type="button" onClick={() => changeSort("confidence")}>{copy.sortConfidence}</button></th>
              <th scope="col">{copy.explanation}</th>
              <th scope="col">{copy.sourceTitle}</th>
            </tr>
          </thead>
          <tbody>
            {window.items.map((relationship) => {
              const source = artistById.get(relationship.sourceArtistId);
              const target = artistById.get(relationship.targetArtistId);
              if (!source || !target) return null;
              return (
                <tr key={relationship.id}>
                  <th scope="row" data-label={copy.explanation}>
                    <button type="button" onClick={(event) => onSelectRelationship(relationship.id, event.currentTarget)}>
                      {localize(relationship.title, locale)}
                    </button>
                  </th>
                  <td data-label={copy.endpoint}>
                    <button type="button" onClick={(event) => onSelectArtist(source.id, event.currentTarget)}>{localize(source.labels, locale)}</button>
                    <span aria-hidden="true">↔</span>
                    <button type="button" onClick={(event) => onSelectArtist(target.id, event.currentTarget)}>{localize(target.labels, locale)}</button>
                  </td>
                  <td data-label={copy.type}>{relationshipTypeLabel(relationship.type, copy)}</td>
                  <td data-label={copy.level}><span className="level-badge">C</span></td>
                  <td data-label={copy.sharedContext}>{relationship.contextIds.map((id) => contextById.get(id)).filter((context): context is ContextRecord => Boolean(context)).map((context) => localize(context.labels, locale)).join(" · ")}</td>
                  <td data-label={copy.confidence} className="tabular-value">{Math.round(relationship.evidenceConfidence * 100)}%</td>
                  <td data-label={copy.explanation}>{localize(relationship.shortExplanation, locale)}</td>
                  <td data-label={copy.sourceTitle}><button type="button" onClick={(event) => onSelectRelationship(relationship.id, event.currentTarget)}>{copy.evidenceSources}</button></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {window.pageCount > 1 ? (
        <nav className="scale-pagination" aria-label={locale === "zh-CN" ? "关系列表分页" : "Relationship table pagination"}>
          <button type="button" disabled={window.page === 1} onClick={() => setRequestedPage(window.page - 1)}>
            {locale === "zh-CN" ? "上一页" : "Previous"}
          </button>
          <span>{window.page} / {window.pageCount} · {window.total}</span>
          <button type="button" disabled={window.page === window.pageCount} onClick={() => setRequestedPage(window.page + 1)}>
            {locale === "zh-CN" ? "下一页" : "Next"}
          </button>
        </nav>
      ) : null}
    </section>
  );
}

export const RelationshipTableView = memo(RelationshipTableViewComponent);
