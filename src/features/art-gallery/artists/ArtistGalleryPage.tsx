import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArtworkImage } from "../../art-constellation/ArtworkImage";
import {
  localize,
  type ArtistSources,
  type RelationshipIndex,
} from "../../art-constellation/types";
import { useI18n } from "../../../i18n/I18nProvider";
import { usePreferences } from "../../../preferences/PreferencesProvider";
import { galleryCopy } from "../copy";
import type { GallerySharedProps } from "../gallery-types";
import { artistPath, artworkPath, factualArtworkAlt } from "../media";
import "./artists.css";

type ArtistGalleryPageProps = GallerySharedProps & { artistId: string };
type ArtistLoad<T> =
  | { artistId: string; status: "loaded"; data: T }
  | { artistId: string; status: "failed" };

export function ArtistGalleryPage({ release, catalog, dataSource, interactions, artistId }: ArtistGalleryPageProps) {
  const { locale } = useI18n();
  const { lowBandwidth } = usePreferences();
  const copy = galleryCopy[locale];
  const artist = release.artists.find((record) => record.id === artistId) ?? null;
  const [relationshipLoad, setRelationshipLoad] = useState<ArtistLoad<RelationshipIndex> | null>(null);
  const [sourceLoad, setSourceLoad] = useState<ArtistLoad<ArtistSources> | null>(null);
  const currentRelationshipLoad = relationshipLoad?.artistId === artistId ? relationshipLoad : null;
  const currentSourceLoad = sourceLoad?.artistId === artistId ? sourceLoad : null;
  const relationshipIndex = currentRelationshipLoad?.status === "loaded" ? currentRelationshipLoad.data : null;
  const artistSources = currentSourceLoad?.status === "loaded" ? currentSourceLoad.data : null;

  useEffect(() => {
    if (!artist) return;
    const controller = new AbortController();
    void Promise.all([
      dataSource.loadRelationshipIndex(controller.signal),
      dataSource.loadArtistSources(artist.id, controller.signal),
    ]).then(([relationshipResult, sourcesResult]) => {
      if (controller.signal.aborted) return;
      setRelationshipLoad(relationshipResult.status === "loaded"
        ? { artistId: artist.id, status: "loaded", data: relationshipResult.data }
        : { artistId: artist.id, status: "failed" });
      setSourceLoad(sourcesResult.status === "loaded"
        ? { artistId: artist.id, status: "loaded", data: sourcesResult.data }
        : { artistId: artist.id, status: "failed" });
    });
    return () => controller.abort();
  }, [artist, dataSource]);

  const artworksById = useMemo(
    () => new Map(catalog.artworks.map((artwork) => [artwork.id, artwork])),
    [catalog.artworks],
  );
  const artworks = useMemo(
    () => artist?.artworkIds.map((artworkId) => artworksById.get(artworkId)).filter((artwork) => artwork !== undefined) ?? [],
    [artist, artworksById],
  );
  const related = useMemo(() => {
    if (!artist || !relationshipIndex) return [];
    const byArtist = new Map<string, typeof relationshipIndex.relationships>();
    for (const relationship of relationshipIndex.relationships) {
      const otherId = relationship.sourceArtistId === artist.id
        ? relationship.targetArtistId
        : relationship.targetArtistId === artist.id
          ? relationship.sourceArtistId
          : null;
      if (!otherId) continue;
      byArtist.set(otherId, [...(byArtist.get(otherId) ?? []), relationship]);
    }
    return [...byArtist.entries()].map(([relatedArtistId, relationships]) => ({
      artist: release.artists.find((record) => record.id === relatedArtistId) ?? null,
      relationships,
    })).filter((entry) => entry.artist !== null);
  }, [artist, relationshipIndex, release]);

  if (!artist) {
    return (
      <main id="main-content" className="gallery-page artist-gallery-page" tabIndex={-1}>
        <section className="gallery-empty-state" aria-labelledby="artist-not-found-title">
          <span aria-hidden="true">∅</span>
          <div>
            <h1 id="artist-not-found-title">{copy.noArtistResults}</h1>
            <Link className="gallery-primary-link" to="/art/artists">{copy.artistIndex}</Link>
          </div>
        </section>
      </main>
    );
  }

  const name = localize(artist.labels, locale);
  const artistTour = interactions.artist_tours.find((tour) => tour.artist_id === artist.id) ?? null;
  const workDates = artworks
    .map((artwork) => artwork.dateDisplay ? localize(artwork.dateDisplay, locale) : null)
    .filter((value): value is string => Boolean(value));

  return (
    <main id="main-content" className="gallery-page artist-gallery-page" tabIndex={-1}>
      <nav className="gallery-breadcrumbs" aria-label={copy.artistGalleryEyebrow}>
        <Link to="/art/artists">{copy.artistIndex}</Link>
        <span aria-hidden="true">/</span>
        <Link to="/art/constellation">{copy.backConstellation}</Link>
        <Link to={`/art/map?artist=${encodeURIComponent(artist.id)}&view=list`}>{locale === "zh-CN" ? "这位艺术家的地点" : "This artist’s places"}</Link>
      </nav>

      <header className="gallery-hero artist-gallery-hero">
        <div>
          <p className="gallery-eyebrow">{copy.artistGalleryEyebrow}</p>
          <h1>{name}</h1>
          <p className="artist-life-display">
            {artist.lifeDisplay ? localize(artist.lifeDisplay, locale) : artist.period}
          </p>
        </div>
        <dl className="gallery-release-tally" aria-label={name}>
          <div><dt>{copy.works}</dt><dd>{artworks.length}</dd></div>
          <div><dt>{copy.approvedWorks}</dt><dd>{artist.approvedMediaArtworkCount}</dd></div>
          <div><dt>{copy.relations}</dt><dd>{artist.relationCount} · C</dd></div>
        </dl>
      </header>

      <div className="artist-gallery-introduction">
        <section aria-labelledby="reviewed-intro-title">
          <p className="gallery-section-number" aria-hidden="true">01</p>
          <h2 id="reviewed-intro-title">{copy.reviewedIntro}</h2>
          <p>{localize(artist.summary, locale)}</p>
        </section>
        <section aria-labelledby="timeline-title">
          <p className="gallery-section-number" aria-hidden="true">02</p>
          <h2 id="timeline-title">{copy.timeline}</h2>
          <dl className="artist-timeline-facts">
            <div><dt>{copy.lifeDates}</dt><dd>{artist.lifeDisplay ? localize(artist.lifeDisplay, locale) : "—"}</dd></div>
            <div><dt>{copy.workRange}</dt><dd>{workDates.length > 0 ? workDates.join(" · ") : "—"}</dd></div>
            <div><dt>{copy.context}</dt><dd>{[artist.period, artist.region, artist.tradition].filter(Boolean).join(" · ")}</dd></div>
            <div><dt>{copy.practice}</dt><dd>{localize(artist.mediaPractice, locale)}</dd></div>
          </dl>
        </section>
      </div>

      {artistTour ? (
        <aside className="artist-tour-entry">
          <p className="eyebrow">{locale === "zh-CN" ? "深度观察导览" : "Deep observation tour"}</p>
          <h2>{localize(artistTour.title, locale)}</h2>
          <p>{localize(artistTour.entry_question, locale)}</p>
          <Link className="gallery-primary-link" to={`/art/tours/${encodeURIComponent(artistTour.id)}`}>
            {locale === "zh-CN" ? "开始固定策展导览" : "Start the fixed curatorial tour"}
          </Link>
        </aside>
      ) : null}

      <section className="artist-formal-works" aria-labelledby="formal-works-title">
        <div className="gallery-section-heading">
          <div>
            <p className="gallery-section-number" aria-hidden="true">03</p>
            <h2 id="formal-works-title">{copy.formalWorks}</h2>
          </div>
          <p>{artworks.length} {copy.works} · {artist.approvedMediaArtworkCount} {copy.approvedWorks}</p>
        </div>
        <ol className="artist-work-grid">
          {artworks.map((artwork, index) => {
            const date = artwork.dateDisplay ? localize(artwork.dateDisplay, locale) : null;
            const materials = artwork.materials.map((value) => localize(value, locale));
            const techniques = artwork.techniques.map((value) => localize(value, locale));
            const subjects = artwork.subjects.map((value) => localize(value, locale));
            return (
              <li key={artwork.id} className="artist-work-card">
                <article>
                  <div className="artist-work-media">
                    <span className="artist-work-number" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
                    <ArtworkImage
                      artworkId={artwork.id}
                      representativeMediaId={artwork.media.representativeMediaId}
                      media={catalog.media}
                      alt={factualArtworkAlt(name, artwork, date, locale)}
                      lowBandwidth={lowBandwidth}
                      variant="representative"
                      noImageText={copy.noImage}
                      lowBandwidthText={copy.lowBandwidthImage}
                      loadImageText={copy.loadImage}
                      imageLoadingText={copy.imageLoading}
                      imageLoadedText={copy.imageLoaded}
                      unavailableText={copy.imageUnavailable}
                      rightsLabel={copy.imageRights}
                      withdrawalLabel={copy.withdrawalStatus}
                      officialSourceLabel={copy.officialSource}
                      officialSourceUrl={artwork.objectUrl}
                    />
                  </div>
                  <div className="artist-work-body">
                    <p className="artist-card-kicker">{date ?? "—"}</p>
                    <h3>{localize(artwork.title, locale)}</h3>
                    <dl className="artist-work-facts">
                      <div><dt>{copy.institution}</dt><dd>{artwork.institution ? localize(artwork.institution, locale) : "—"}</dd></div>
                      <div><dt>{copy.accession}</dt><dd>{artwork.accessionNumber ?? "—"}</dd></div>
                      <div><dt>{copy.materials}</dt><dd>{materials.length > 0 ? materials.join(" · ") : "—"}</dd></div>
                      <div><dt>{copy.techniques}</dt><dd>{techniques.length > 0 ? techniques.join(" · ") : "—"}</dd></div>
                      <div><dt>{copy.subjects}</dt><dd>{subjects.length > 0 ? subjects.join(" · ") : "—"}</dd></div>
                      <div><dt>{copy.imageDecision}</dt><dd><code>{artwork.media.decision}</code></dd></div>
                      <div><dt>{copy.metadataRule}</dt><dd><code>{artwork.metadataLicense}</code></dd></div>
                    </dl>
                    {artwork.limitations ? <p className="artist-work-limit">{localize(artwork.limitations, locale)}</p> : null}
                    <div className="artist-work-actions">
                      <Link className="gallery-primary-link" to={artworkPath(artwork.id)}>{copy.viewArtwork}</Link>
                      {artwork.objectUrl ? <a href={artwork.objectUrl}>{copy.officialSource}</a> : null}
                    </div>
                  </div>
                </article>
              </li>
            );
          })}
        </ol>
      </section>

      <div className="artist-gallery-reference-grid">
        <section aria-labelledby="related-artists-title">
          <p className="gallery-section-number" aria-hidden="true">04</p>
          <h2 id="related-artists-title">{copy.relatedArtists}</h2>
          <p className="artist-related-boundary">{localize(release.summary.semantics, locale)}</p>
          {!currentRelationshipLoad ? <p role="status">{copy.loading}</p> : currentRelationshipLoad.status === "failed" ? (
            <p role="alert">{copy.relatedUnavailable}</p>
          ) : related.length > 0 ? (
            <ul className="artist-related-list">
              {related.map((entry) => (
                <li key={entry.artist!.id}>
                  <Link to={artistPath(entry.artist!.id)}>{localize(entry.artist!.labels, locale)}</Link>
                  <span>{entry.relationships.length} · C</span>
                  <small>{entry.relationships.map((relationship) => localize(relationship.title, locale)).join(" · ")}</small>
                </li>
              ))}
            </ul>
          ) : <p>{copy.noRelatedArtists}</p>}
        </section>

        <section aria-labelledby="artist-sources-title">
          <p className="gallery-section-number" aria-hidden="true">05</p>
          <h2 id="artist-sources-title">{copy.sourceRights}</h2>
          <dl className="artist-review-facts">
            <div><dt>{copy.reviewRecord}</dt><dd>{artist.reviewer} · {artist.reviewDate}</dd></div>
            <div><dt>{copy.metadataRule}</dt><dd>{[...new Set(artworks.map((artwork) => artwork.metadataLicense))].join(" · ")}</dd></div>
          </dl>
          {!currentSourceLoad ? <p role="status">{copy.loading}</p> : currentSourceLoad.status === "failed" ? (
            <>
              <p role="alert">{copy.sourcesUnavailable}</p>
              <ul className="artist-source-list">
                {artist.sourceIds.map((sourceId) => <li key={sourceId}><code>{sourceId}</code></li>)}
              </ul>
            </>
          ) : artistSources?.sources.length ? (
            <ul className="artist-source-list">
              {artistSources.sources.map((source) => (
                <li key={source.id}>
                  <a href={source.officialUrl}>{source.title}</a>
                  <span>{source.publisher} · {source.license}</span>
                </li>
              ))}
            </ul>
          ) : (
            <ul className="artist-source-list">
              {artist.sourceIds.map((sourceId) => <li key={sourceId}><code>{sourceId}</code></li>)}
            </ul>
          )}
        </section>
      </div>

      <nav className="gallery-closing-links" aria-label={copy.artistGalleryEyebrow}>
        <Link className="gallery-primary-link" to="/art/constellation">{copy.backConstellation}</Link>
        <Link to={`/art/paths?from=${encodeURIComponent(artist.id)}&to=${encodeURIComponent(release.artists.find((candidate) => candidate.id !== artist.id)?.id ?? "")}&mode=comparison&maxHops=6&path=1&view=text`}>
          {locale === "zh-CN" ? "从这位艺术家查找路径" : "Find paths from this artist"}
        </Link>
        <Link to="/art/artists">{copy.artistIndex}</Link>
        <Link to={`/art/map?artist=${encodeURIComponent(artist.id)}&view=timeline`}>{locale === "zh-CN" ? "在时间线中查看地点" : "View places on the timeline"}</Link>
      </nav>
    </main>
  );
}
