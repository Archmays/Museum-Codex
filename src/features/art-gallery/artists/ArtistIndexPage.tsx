import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArtworkImage } from "../../art-constellation/ArtworkImage";
import { localize, type ArtistRecord, type ArtworkRecord } from "../../art-constellation/types";
import { useI18n } from "../../../i18n/I18nProvider";
import { usePreferences } from "../../../preferences/PreferencesProvider";
import { galleryCopy, fillCopy } from "../copy";
import type { GallerySharedProps } from "../gallery-types";
import { artistPath, factualArtworkAlt } from "../media";
import "./artists.css";

type ImageFilter = "all" | "with-image" | "without-image";

function normalized(value: string) {
  return value
    .normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .toLocaleLowerCase()
    .trim();
}

function representativeArtwork(
  artist: ArtistRecord,
  artworksById: Map<string, ArtworkRecord>,
  mediaArtworkById: Map<string, string>,
) {
  const representativeArtworkId = artist.representativeMediaId
    ? mediaArtworkById.get(artist.representativeMediaId)
    : null;
  if (representativeArtworkId) return artworksById.get(representativeArtworkId) ?? null;
  return artist.artworkIds
    .map((artworkId) => artworksById.get(artworkId))
    .find((artwork) => artwork?.media.decision === "approved_self_hosted") ?? null;
}

export function ArtistIndexPage({ release, catalog }: GallerySharedProps) {
  const { locale } = useI18n();
  const { lowBandwidth } = usePreferences();
  const copy = galleryCopy[locale];
  const [query, setQuery] = useState("");
  const [period, setPeriod] = useState("all");
  const [imageFilter, setImageFilter] = useState<ImageFilter>("all");
  const artworksById = useMemo(
    () => new Map(catalog.artworks.map((artwork) => [artwork.id, artwork])),
    [catalog.artworks],
  );
  const mediaArtworkById = useMemo(
    () => new Map(catalog.media.map((asset) => [asset.id, asset.artworkId])),
    [catalog.media],
  );
  const periods = useMemo(
    () => [...new Set(release.artists.map((artist) => artist.period))],
    [release.artists],
  );
  const artistOrdinals = useMemo(
    () => new Map(release.artists.map((artist, index) => [artist.id, index + 1])),
    [release.artists],
  );

  const artists = useMemo(() => {
    const normalizedQuery = normalized(query);
    return release.artists.filter((artist) => {
      const matchesPeriod = period === "all" || artist.period === period;
      const hasImage = artist.approvedMediaArtworkCount > 0 && Boolean(artist.representativeMediaId);
      const matchesImage = imageFilter === "all"
        || (imageFilter === "with-image" ? hasImage : !hasImage);
      const searchText = normalized([
        localize(artist.labels, locale),
        artist.labels.en,
        artist.labels["zh-Hans"],
        ...artist.aliases,
        artist.period,
        artist.region,
        artist.tradition ?? "",
        localize(artist.mediaPractice, locale),
      ].join(" "));
      return matchesPeriod && matchesImage && (!normalizedQuery || searchText.includes(normalizedQuery));
    });
  }, [imageFilter, locale, period, query, release.artists]);

  const filtersActive = query.length > 0 || period !== "all" || imageFilter !== "all";
  const clearFilters = () => {
    setQuery("");
    setPeriod("all");
    setImageFilter("all");
  };

  return (
    <main id="main-content" className="gallery-page artist-index-page" tabIndex={-1}>
      <nav className="gallery-breadcrumbs" aria-label={copy.artistIndex}>
        <Link to="/art">{copy.backFoyer}</Link>
        <span aria-hidden="true">/</span>
        <Link to="/art/constellation">{copy.backConstellation}</Link>
      </nav>

      <header className="gallery-hero artist-index-hero">
        <p className="gallery-eyebrow">{copy.artistIndexEyebrow}</p>
        <div>
          <h1>{copy.artistIndexTitle}</h1>
          <p>{copy.artistIndexIntro}</p>
        </div>
        <dl className="gallery-release-tally" aria-label={copy.artistIndex}>
          <div><dt>{copy.works}</dt><dd>{release.summary.artworkCount}</dd></div>
          <div><dt>{copy.approvedWorks}</dt><dd>{release.summary.approvedMediaArtworkCount}</dd></div>
          <div><dt>{copy.relations}</dt><dd>{release.summary.relationshipCount}</dd></div>
        </dl>
      </header>

      <section className="gallery-filter-panel" aria-labelledby="artist-filter-title">
        <h2 id="artist-filter-title" className="sr-only">{copy.artistIndex}</h2>
        <div className="artist-filter-grid">
          <label>
            <span>{copy.artistSearch}</span>
            <input
              type="search"
              value={query}
              placeholder={copy.artistSearchPlaceholder}
              onChange={(event) => setQuery(event.currentTarget.value)}
            />
          </label>
          <label>
            <span>{copy.periodFilter}</span>
            <select value={period} onChange={(event) => setPeriod(event.currentTarget.value)}>
              <option value="all">{copy.allPeriods}</option>
              {periods.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <label>
            <span>{copy.imageFilter}</span>
            <select
              value={imageFilter}
              onChange={(event) => setImageFilter(event.currentTarget.value as ImageFilter)}
            >
              <option value="all">{copy.allImageStates}</option>
              <option value="with-image">{copy.withImage}</option>
              <option value="without-image">{copy.withoutImage}</option>
            </select>
          </label>
          <button type="button" onClick={clearFilters} disabled={!filtersActive}>{copy.clearFilters}</button>
        </div>
        <p className="artist-results-status" role="status" aria-live="polite">
          {fillCopy(copy.artistResults, { count: artists.length })}
        </p>
      </section>

      {artists.length > 0 ? (
        <ol className="artist-index-grid" aria-label={copy.artistIndex}>
          {artists.map((artist) => {
            const representative = representativeArtwork(artist, artworksById, mediaArtworkById);
            const name = localize(artist.labels, locale);
            const date = representative?.dateDisplay ? localize(representative.dateDisplay, locale) : null;
            return (
              <li key={artist.id} className="artist-index-card" data-image-state={representative ? "approved" : "no-image"}>
                <article>
                  <div className="artist-card-ordinal" aria-hidden="true">
                    {String(artistOrdinals.get(artist.id) ?? 0).padStart(2, "0")}
                  </div>
                  <ArtworkImage
                    artworkId={representative?.id ?? artist.id}
                    representativeMediaId={representative?.media.representativeMediaId ?? null}
                    media={representative ? catalog.media : []}
                    alt={representative ? factualArtworkAlt(name, representative, date, locale) : name}
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
                    officialSourceLabel={copy.officialSource}
                    officialSourceUrl={representative?.objectUrl ?? null}
                  />
                  <div className="artist-card-body">
                    <p className="artist-card-kicker">{artist.period}</p>
                    <h2><Link to={artistPath(artist.id)}>{name}</Link></h2>
                    <p className="artist-card-summary">{localize(artist.summary, locale)}</p>
                    <dl className="artist-card-facts">
                      <div><dt>{copy.lifeDates}</dt><dd>{artist.lifeDisplay ? localize(artist.lifeDisplay, locale) : "—"}</dd></div>
                      <div><dt>{copy.context}</dt><dd>{[artist.region, artist.tradition].filter(Boolean).join(" · ")}</dd></div>
                      <div><dt>{copy.practice}</dt><dd>{localize(artist.mediaPractice, locale)}</dd></div>
                      <div><dt>{copy.works}</dt><dd>{artist.artworkIds.length}</dd></div>
                      <div><dt>{copy.approvedWorks}</dt><dd>{artist.approvedMediaArtworkCount}</dd></div>
                      <div><dt>{copy.relations}</dt><dd>{artist.relationCount} · C</dd></div>
                    </dl>
                    <Link className="gallery-primary-link" to={artistPath(artist.id)}>{copy.openArtist}</Link>
                  </div>
                </article>
              </li>
            );
          })}
        </ol>
      ) : (
        <section className="gallery-empty-state" aria-labelledby="artist-empty-title">
          <span aria-hidden="true">∅</span>
          <div>
            <h2 id="artist-empty-title">{copy.noArtistResults}</h2>
            <button type="button" onClick={clearFilters}>{copy.clearFilters}</button>
          </div>
        </section>
      )}
    </main>
  );
}
