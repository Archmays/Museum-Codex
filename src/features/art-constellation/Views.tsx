import { memo, useEffect, useMemo, useState, type ComponentType } from "react";
import type { Locale, Translation } from "../../i18n/translations";
import { relationshipTypeLabel } from "./labels";
import type { MatchReason } from "./model";
import { localize, type ArtistRecord, type ContextRecord, type LayoutNode, type RelationshipRecord } from "./types";

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

function fill(template: string, values: Record<string, string | number>) {
  return Object.entries(values).reduce((text, [key, value]) => text.replace(`{${key}}`, String(value)), template);
}

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

type GraphRendererProps = {
  artists: ArtistRecord[];
  relationships: RelationshipRecord[];
  layout: LayoutNode[];
  locale: Locale;
  focusArtistId: string | null;
  selectedRelationshipId: string | null;
  relatedArtistIds: Set<string>;
  onSelectArtist: (artistId: string) => void;
  onSelectRelationship: (relationshipId: string) => void;
  onReady: () => void;
  onUnavailable: (reason: "unavailable" | "context-lost") => void;
};

function GraphViewComponent({
  artists,
  relationships,
  locale,
  copy,
  focusArtistId,
  selectedRelationshipId,
  matchReasons,
  relationshipIndexLoaded,
  layout,
  relatedArtistIds,
  onSelectArtist,
  onSelectRelationship,
  onRendererReady,
  onRendererUnavailable,
}: SharedViewProps & {
  layout: LayoutNode[];
  relatedArtistIds: Set<string>;
  onRendererReady: () => void;
  onRendererUnavailable: (reason: "unavailable" | "context-lost") => void;
}) {
  const [Renderer, setRenderer] = useState<ComponentType<GraphRendererProps> | null>(null);

  useEffect(() => {
    let active = true;
    void import("./SigmaGraphRenderer")
      .then((module) => {
        if (active) setRenderer(() => module.default);
      })
      .catch(() => {
        if (active) onRendererUnavailable("unavailable");
      });
    return () => {
      active = false;
    };
  }, [onRendererUnavailable]);

  return (
    <section className="constellation-graph-view" aria-label={copy.graphView}>
      <div className="constellation-graph-stage">
        {Renderer ? (
          <Renderer
            artists={artists}
            relationships={relationships}
            layout={layout}
            locale={locale}
            focusArtistId={focusArtistId}
            selectedRelationshipId={selectedRelationshipId}
            relatedArtistIds={relatedArtistIds}
            onSelectArtist={(artistId) => onSelectArtist(artistId)}
            onSelectRelationship={(relationshipId) => onSelectRelationship(relationshipId)}
            onReady={onRendererReady}
            onUnavailable={onRendererUnavailable}
          />
        ) : (
          <p className="constellation-graph-loading" role="status">{copy.graphLoading}</p>
        )}
        <div className="constellation-graph-caption">
          <span className="edge-sample edge-sample-c" aria-hidden="true" />
          <span>{copy.levelCCount}</span>
        </div>
      </div>
      <p className="constellation-graph-instruction">
        {focusArtistId ? copy.distanceNotice : copy.graphInitial}
      </p>
      <nav className="artist-navigator" aria-label={copy.artistNavigator}>
        {artists.map((artist, index) => {
          const name = localize(artist.labels, locale);
          const count = relationshipCount(artist, relationships, relationshipIndexLoaded);
          const reason = matchReasonLabel(matchReasons.get(artist.id), copy);
          return (
            <button
              key={artist.id}
              type="button"
              className={artist.id === focusArtistId ? "is-selected" : undefined}
              aria-pressed={artist.id === focusArtistId}
              aria-label={fill(copy.selectArtist, { name })}
              onClick={(event) => onSelectArtist(artist.id, event.currentTarget)}
            >
              <span>{String(index + 1).padStart(2, "0")}</span>
              <strong>{name}</strong>
              <small>{reason ?? `${count} C`}</small>
            </button>
          );
        })}
      </nav>
    </section>
  );
}

export const GraphView = memo(GraphViewComponent);

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
  return (
    <section className="artist-list-view" aria-label={copy.listView}>
      <ol>
        {artists.map((artist, index) => {
          const name = localize(artist.labels, locale);
          const reason = matchReasonLabel(matchReasons.get(artist.id), copy);
          const count = relationshipCount(artist, relationships, relationshipIndexLoaded);
          return (
            <li key={artist.id} className={artist.id === focusArtistId ? "is-selected" : undefined}>
              <span className="artist-list-index">{String(index + 1).padStart(2, "0")}</span>
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
            {sorted.map((relationship) => {
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
    </section>
  );
}

export const RelationshipTableView = memo(RelationshipTableViewComponent);
