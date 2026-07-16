import { forwardRef, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import type { Locale, Translation } from "../../i18n/translations";
import {
  localize,
  type ArtConstellationRelease,
  type ArtistSources,
  type RelationshipDetails,
  type RelationshipIndex,
  type RightsDetails,
  type SourceRecord,
} from "./types";
import { relationshipTypeLabel } from "./labels";
import { ArtworkImage } from "./ArtworkImage";

type Copy = Translation["constellation"];

export type PanelLoadState<T> =
  | { status: "idle" | "loading" }
  | { status: "loaded"; data: T }
  | { status: "failed" };

export type OpenPanel =
  | { kind: "artist"; id: string }
  | { kind: "relationship"; id: string }
  | { kind: "rights" };

type DetailPanelProps = {
  panel: OpenPanel | null;
  release: ArtConstellationRelease;
  relationshipIndex: PanelLoadState<RelationshipIndex>;
  artistSources: PanelLoadState<ArtistSources>;
  relationshipDetails: PanelLoadState<RelationshipDetails>;
  rightsDetails: PanelLoadState<RightsDetails>;
  locale: Locale;
  copy: Copy;
  lowBandwidth: boolean;
  onClose: () => void;
  onRetryIndex: () => void;
  onRetryArtistSources: () => void;
  onRetryRelationship: () => void;
  onRetryRights: () => void;
  onSelectRelationship: (relationshipId: string, trigger: HTMLElement) => void;
};

function LoadingState({ children }: { children: string }) {
  return <p className="panel-load-state" role="status">{children}</p>;
}

function FailedState({ copy, onRetry }: { copy: Copy; onRetry: () => void }) {
  return (
    <div className="panel-load-state is-error" role="alert">
      <p>{copy.detailError}</p>
      <button type="button" onClick={onRetry}>{copy.retry}</button>
    </div>
  );
}

function Sources({ sources, locale, copy }: { sources: SourceRecord[]; locale: Locale; copy: Copy }) {
  if (sources.length === 0) return null;
  return (
    <section className="panel-section source-list" aria-labelledby="panel-sources-title">
      <h3 id="panel-sources-title">{copy.sourceTitle}</h3>
      <ol>
        {sources.map((source) => (
          <li key={source.id}>
            <h4>{source.title}</h4>
            <p>{source.publisher}{source.date ? ` · ${source.date}` : ""}</p>
            {source.locator ? <p>{localize(source.locator, locale)}</p> : null}
            <dl>
              <div><dt>{copy.sourceLicense}</dt><dd>{source.license}</dd></div>
              <div><dt>{copy.sourceAttribution}</dt><dd>{source.attribution}</dd></div>
            </dl>
            <a href={source.officialUrl}>{copy.sourceVisit}</a>
          </li>
        ))}
      </ol>
    </section>
  );
}

function ArtistPanel({
  id,
  release,
  relationshipIndex,
  artistSources,
  locale,
  copy,
  lowBandwidth,
  onRetryIndex,
  onRetryArtistSources,
  onSelectRelationship,
}: Omit<DetailPanelProps, "panel" | "onClose" | "relationshipDetails" | "rightsDetails" | "onRetryRelationship" | "onRetryRights"> & { id: string }) {
  const [detailsReadyId, setDetailsReadyId] = useState<string | null>(null);
  useEffect(() => {
    const frame = requestAnimationFrame(() => setDetailsReadyId(id));
    return () => cancelAnimationFrame(frame);
  }, [id]);
  const detailsReady = detailsReadyId === id;
  const artist = release.artists.find((candidate) => candidate.id === id);
  const relationships = detailsReady && relationshipIndex.status === "loaded"
    ? relationshipIndex.data.relationships.filter(
        (relationship) => relationship.sourceArtistId === id || relationship.targetArtistId === id,
      )
    : [];
  const representativeArtwork = artistSources.status === "loaded"
    ? artistSources.data.artworks.find((artwork) => artwork.media.mediaIds.includes(artist?.representativeMediaId ?? ""))
      ?? artistSources.data.artworks[0]
      ?? null
    : null;
  if (!artist) return <FailedState copy={copy} onRetry={onRetryIndex} />;
  return (
    <>
      <p className="panel-kicker">{copy.learnArtist}</p>
      <h2 id="constellation-panel-content-title">{localize(artist.labels, locale)}</h2>
      {!detailsReady ? (
        <LoadingState>{copy.artistDetailsLoading}</LoadingState>
      ) : (
        <>
          <p className="panel-lede">{localize(artist.summary, locale)}</p>
          <dl className="panel-facts">
            {artist.lifeDisplay ? <div><dt>{copy.periodRegion}</dt><dd>{localize(artist.lifeDisplay, locale)} · {artist.period} · {artist.region}</dd></div> : null}
            {artist.tradition ? <div><dt>{copy.tradition}</dt><dd>{artist.tradition}</dd></div> : null}
            <div><dt>{copy.practice}</dt><dd>{localize(artist.mediaPractice, locale)}</dd></div>
            <div><dt>{copy.relatedRelationships}</dt><dd>{artist.relationCount} · C</dd></div>
            <div><dt>{copy.reviewRecord}</dt><dd>{artist.reviewer} · {artist.reviewDate}</dd></div>
            <div>
              <dt>{copy.releaseLabel}</dt>
              <dd>{release.version}</dd>
            </div>
          </dl>
          <p className="gallery-preparing">{copy.galleryPreparing}</p>
          <p className="gallery-preparing">
            <Link to={`/art/paths?from=${encodeURIComponent(artist.id)}&to=${encodeURIComponent(release.artists.find((candidate) => candidate.id !== artist.id)?.id ?? "")}&mode=comparison&maxHops=6&path=1&view=text`}>
              {locale === "zh-CN" ? "以这位艺术家为起点查找可解释路径" : "Find explainable paths from this artist"}
            </Link>
          </p>
          {artistSources.status === "loaded" && representativeArtwork ? (
            <section className="panel-section artist-representative" aria-labelledby="artist-representative-title">
              <h3 id="artist-representative-title">{localize(representativeArtwork.title, locale)}</h3>
              <ArtworkImage
                artworkId={representativeArtwork.id}
                representativeMediaId={artist.representativeMediaId}
                media={artistSources.data.media}
                alt={`${localize(representativeArtwork.title, locale)} — ${localize(artist.labels, locale)}`}
                lowBandwidth={lowBandwidth}
                noImageText={copy.noImage}
                lowBandwidthText={copy.lowBandwidthImage}
                loadImageText={copy.loadImage}
                imageLoadingText={copy.imageLoading}
                imageLoadedText={copy.imageLoaded}
                unavailableText={copy.imageUnavailable}
                rightsLabel={copy.imageRights}
                withdrawalLabel={copy.withdrawalStatus}
                officialSourceLabel={copy.sourceVisit}
                officialSourceUrl={representativeArtwork.objectUrl}
              />
            </section>
          ) : null}
          <section className="panel-section" aria-labelledby="artist-relations-title">
            <h3 id="artist-relations-title">{copy.relatedRelationships}</h3>
            {relationshipIndex.status === "loading" || relationshipIndex.status === "idle" ? (
              <LoadingState>{copy.relationsLoading}</LoadingState>
            ) : relationshipIndex.status === "failed" ? (
              <FailedState copy={copy} onRetry={onRetryIndex} />
            ) : (
              <ul className="related-relation-list">
                {relationships.map((relationship) => (
                  <li key={relationship.id}>
                    <button type="button" onClick={(event) => onSelectRelationship(relationship.id, event.currentTarget)}>
                      <span>C · {relationshipTypeLabel(relationship.type, copy)}</span>
                      <strong>{localize(relationship.title, locale)}</strong>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
          {artistSources.status === "loaded" ? (
            <Sources sources={artistSources.data.sources} locale={locale} copy={copy} />
          ) : artistSources.status === "failed" ? (
            <FailedState copy={copy} onRetry={onRetryArtistSources} />
          ) : (
            <LoadingState>{copy.sourcesLoading}</LoadingState>
          )}
        </>
      )}
    </>
  );
}

function RelationshipPanel({
  id,
  release,
  relationshipIndex,
  relationshipDetails,
  locale,
  copy,
  lowBandwidth,
  onRetryRelationship,
}: Pick<DetailPanelProps, "release" | "relationshipIndex" | "relationshipDetails" | "locale" | "copy" | "lowBandwidth" | "onRetryRelationship"> & { id: string }) {
  const relationship = relationshipIndex.status === "loaded"
    ? relationshipIndex.data.relationships.find((candidate) => candidate.id === id)
    : null;
  const artistById = useMemo(() => new Map(release.artists.map((artist) => [artist.id, artist])), [release.artists]);
  if (!relationship) return <LoadingState>{copy.relationsLoading}</LoadingState>;
  const sourceArtist = artistById.get(relationship.sourceArtistId);
  const targetArtist = artistById.get(relationship.targetArtistId);
  const details = relationshipDetails.status === "loaded" ? relationshipDetails.data : null;
  return (
    <>
      <p className="panel-kicker">C · {relationshipTypeLabel(relationship.type, copy)}</p>
      <h2 id="constellation-panel-content-title">{localize(relationship.title, locale)}</h2>
      <p className="panel-endpoints">
        {sourceArtist ? localize(sourceArtist.labels, locale) : ""}
        <span aria-hidden="true"> ↔ </span>
        {targetArtist ? localize(targetArtist.labels, locale) : ""}
      </p>
      <p className="panel-lede">{localize(relationship.shortExplanation, locale)}</p>
      <dl className="panel-facts">
        <div><dt>{copy.level}</dt><dd>C · {copy.levelC}</dd></div>
        <div><dt>{copy.confidence}</dt><dd>{Math.round(relationship.evidenceConfidence * 100)}%</dd></div>
        <div><dt>{copy.curatorialRelevance}</dt><dd>{Math.round(relationship.curatorialRelevance * 100)}%</dd></div>
        <div><dt>{copy.historicalStrength}</dt><dd>{copy.notAsserted}</dd></div>
        <div><dt>{copy.computationalSimilarity}</dt><dd>{copy.notIncluded}</dd></div>
        <div><dt>{copy.reviewRecord}</dt><dd>{relationship.reviewer} · {relationship.reviewDate}</dd></div>
        <div>
          <dt>{copy.releaseLabel}</dt>
          <dd>{release.version}</dd>
        </div>
      </dl>
      <section className="panel-section">
        <h3>{copy.whatItMeans}</h3>
        <p>{localize(relationship.whatItMeans, locale)}</p>
      </section>
      <section className="panel-section is-caution">
        <h3>{copy.doesNotMean}</h3>
        <p>{localize(relationship.doesNotMean, locale)}</p>
      </section>
      {relationship.limitations ? (
        <section className="panel-section">
          <h3>{copy.limitations}</h3>
          <p>{localize(relationship.limitations, locale)}</p>
        </section>
      ) : null}
      <section className="panel-section identifier-closure" aria-labelledby="relation-claim-title">
        <h3 id="relation-claim-title">{copy.claimIds}</h3>
        <ul>{relationship.claimIds.map((claimId) => <li key={claimId}><code>{claimId}</code></li>)}</ul>
        <h3>{copy.evidenceIds}</h3>
        <ul>{relationship.evidenceIds.map((evidenceId) => <li key={evidenceId}><code>{evidenceId}</code></li>)}</ul>
      </section>
      {details ? (
        <>
          <section className="panel-section" aria-labelledby="relation-context-title">
            <h3 id="relation-context-title">{copy.sharedContext}</h3>
            <ul className="context-chips">
              {details.contexts.map((context) => <li key={context.id}>{localize(context.labels, locale)}</li>)}
            </ul>
          </section>
          <section className="panel-section" aria-labelledby="relation-artworks-title">
            <h3 id="relation-artworks-title">{copy.supportingWorks}</h3>
            <ol className="artwork-metadata-list">
              {details.artworks.map((artwork) => {
                const sourceAttributions = details.sources
                  .filter((source) => artwork.sourceIds.includes(source.id))
                  .map((source) => source.attribution);
                const artworkArtist = artistById.get(artwork.artistId);
                return <li key={artwork.id}>
                  <h4>{localize(artwork.title, locale)}</h4>
                  <ArtworkImage
                    artworkId={artwork.id}
                    representativeMediaId={artwork.media.representativeMediaId}
                    media={details.media}
                    alt={`${localize(artwork.title, locale)}${artworkArtist ? ` — ${localize(artworkArtist.labels, locale)}` : ""}`}
                    lowBandwidth={lowBandwidth}
                    variant="thumbnail"
                    noImageText={copy.noImage}
                    lowBandwidthText={copy.lowBandwidthImage}
                    loadImageText={copy.loadImage}
                    imageLoadingText={copy.imageLoading}
                    imageLoadedText={copy.imageLoaded}
                    unavailableText={copy.imageUnavailable}
                    rightsLabel={copy.imageRights}
                    withdrawalLabel={copy.withdrawalStatus}
                    officialSourceLabel={copy.sourceVisit}
                    officialSourceUrl={artwork.objectUrl}
                  />
                  <p>
                    {[artwork.dateDisplay && localize(artwork.dateDisplay, locale), artwork.mediumDisplay && localize(artwork.mediumDisplay, locale), artwork.institution && localize(artwork.institution, locale)]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                  <dl className="artwork-facts">
                    {artwork.accessionNumber ? <div><dt>{copy.accessionNumber}</dt><dd>{artwork.accessionNumber}</dd></div> : null}
                    <div><dt>{copy.materials}</dt><dd>{artwork.materials.map((item) => localize(item, locale)).join(" · ")}</dd></div>
                    <div><dt>{copy.techniques}</dt><dd>{artwork.techniques.map((item) => localize(item, locale)).join(" · ")}</dd></div>
                    <div><dt>{copy.subjects}</dt><dd>{artwork.subjects.map((item) => localize(item, locale)).join(" · ")}</dd></div>
                    <div><dt>{copy.metadataLicenseRule}</dt><dd><code>{artwork.metadataLicense}</code></dd></div>
                    {sourceAttributions.length ? <div><dt>{copy.sourceAttribution}</dt><dd>{sourceAttributions.join(" · ")}</dd></div> : null}
                  </dl>
                  {artwork.limitations ? <p>{localize(artwork.limitations, locale)}</p> : null}
                  {artwork.objectUrl ? <a href={artwork.objectUrl}>{copy.sourceVisit}</a> : null}
                </li>;
              })}
            </ol>
          </section>
          <section className="panel-section" aria-labelledby="relation-evidence-title">
            <h3 id="relation-evidence-title">{copy.evidenceSources}</h3>
            <ol className="evidence-list">
              {details.evidence.map((evidence) => (
                <li key={evidence.id}>
                  <p>{localize(evidence.summary, locale)}</p>
                  <p>{localize(evidence.reliabilityNote, locale)}</p>
                  {evidence.locator ? <small>{evidence.locator}</small> : null}
                </li>
              ))}
            </ol>
          </section>
          <Sources sources={details.sources} locale={locale} copy={copy} />
        </>
      ) : relationshipDetails.status === "failed" ? (
        <FailedState copy={copy} onRetry={onRetryRelationship} />
      ) : (
        <LoadingState>{copy.detailsLoading}</LoadingState>
      )}
    </>
  );
}

function RightsPanel({ rightsDetails, locale, copy, onRetryRights }: Pick<DetailPanelProps, "rightsDetails" | "locale" | "copy" | "onRetryRights">) {
  if (rightsDetails.status !== "loaded") {
    return rightsDetails.status === "failed"
      ? <FailedState copy={copy} onRetry={onRetryRights} />
      : <LoadingState>{copy.rightsLoading}</LoadingState>;
  }
  const { rights, notices } = rightsDetails.data;
  return (
    <>
      <p className="panel-kicker">{copy.rightsPanel}</p>
      <h2 id="constellation-panel-content-title">{copy.rightsPanel}</h2>
      <p className="panel-lede">{copy.rightsNoMedia}</p>
      <dl className="panel-facts">
        <div><dt>{copy.codeRights}</dt><dd>{localize(rights.codeRights, locale)}</dd></div>
        <div><dt>{copy.contentRights}</dt><dd>{localize(rights.originalContentRights, locale)}</dd></div>
        <div><dt>{copy.metadataRights}</dt><dd>{rights.thirdPartyMetadata.map((statement) => localize(statement, locale)).join(" · ")}</dd></div>
        <div><dt>{copy.mediaRights}</dt><dd>{localize(rights.mediaStatement, locale)}</dd></div>
        <div><dt>{copy.supportingWorks}</dt><dd>{rights.approvedMediaArtworks} / {rights.approvedMediaArtworks + rights.noImageArtworks}</dd></div>
        <div><dt>{copy.imageRights}</dt><dd>{rights.mediaCount} · {rights.mediaBytes.toLocaleString(locale)} bytes</dd></div>
      </dl>
      <section className="panel-section notice-list">
        <h3>{copy.noticesLink}</h3>
        <ol>
          {notices.map((notice) => (
            <li key={notice.id}>
              <p>{notice.notice}</p>
              {notice.licenseIdentifiers.length ? <p>{notice.licenseIdentifiers.join(" · ")}</p> : null}
              {notice.attributions.map((attribution) => <p key={attribution}>{attribution}</p>)}
              {notice.sourceUrl ? <a href={notice.sourceUrl}>{copy.sourceVisit}</a> : null}
            </li>
          ))}
        </ol>
      </section>
      <div className="panel-actions">
        <a href={`${import.meta.env.BASE_URL}THIRD_PARTY_NOTICES.md`}>{copy.noticesLink}</a>
        <a href={rights.rightsRequestUrl}>{copy.rightsRequest}</a>
      </div>
    </>
  );
}

export const DetailPanel = forwardRef<HTMLElement, DetailPanelProps>(function DetailPanel(props, panelElementRef) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const panel = props.panel;
  const panelKey = panel === null ? "closed" : panel.kind === "rights" ? panel.kind : `${panel.kind}:${panel.id}`;
  useEffect(() => {
    if (!panel) return;
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0;
      scrollRef.current.hidden = false;
    }
    scrollRef.current?.removeAttribute("aria-busy");
    scrollRef.current?.querySelector<HTMLElement>("#constellation-panel-content-title")?.removeAttribute("hidden");
    closeRef.current?.focus({ preventScroll: true });
  }, [panel, panelKey]);
  const accessibleTitle = panel?.kind === "artist"
    ? props.copy.artistPanel
    : panel?.kind === "relationship"
      ? props.copy.relationshipPanel
      : panel?.kind === "rights" ? props.copy.rightsPanel : "";
  return (
    <aside
      ref={panelElementRef}
      className="constellation-detail-panel"
      hidden={!panel}
      aria-hidden={panel ? undefined : true}
      aria-labelledby={panel ? "constellation-panel-accessible-title" : undefined}
      data-panel-kind={panel?.kind}
      data-panel-id={panel && panel.kind !== "rights" ? panel.id : undefined}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.preventDefault();
          props.onClose();
        }
      }}
    >
      <h2 id="constellation-panel-accessible-title" className="sr-only">{accessibleTitle}</h2>
      <button ref={closeRef} className="panel-close" type="button" onClick={props.onClose}>
        <span aria-hidden="true">×</span>
        <span>{props.copy.closePanel}</span>
      </button>
      <div ref={scrollRef} className="panel-scroll">
        {panel?.kind === "artist" ? <ArtistPanel {...props} id={panel.id} /> : null}
        {panel?.kind === "relationship" ? <RelationshipPanel {...props} id={panel.id} /> : null}
        {panel?.kind === "rights" ? <RightsPanel {...props} /> : null}
        {panel === null ? <LoadingState>{props.copy.artistDetailsLoading}</LoadingState> : null}
      </div>
    </aside>
  );
});
