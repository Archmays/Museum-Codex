import { useEffect, useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useI18n } from "../../../i18n/I18nProvider";
import type { Locale } from "../../../i18n/translations";
import { usePreferences } from "../../../preferences/PreferencesProvider";
import {
  localize,
  type ArtworkRecord,
  type MediaAsset,
} from "../../art-constellation/types";
import { ArtworkZoom } from "../artwork/ArtworkZoom";
import { galleryCopy } from "../copy";
import type { GallerySharedProps } from "../gallery-types";
import { mediaForArtwork } from "../media";
import "../artwork/artwork.css";
import "./compare.css";

type CompareSlot = "left" | "right";

function localizedList(items: ArtworkRecord["materials"], locale: Locale) {
  return items.length > 0 ? items.map((item) => localize(item, locale)).join(" · ") : "—";
}

function approvedMediaForArtwork(artwork: ArtworkRecord, media: MediaAsset[]) {
  if (artwork.media.decision !== "approved_self_hosted") return [];
  return mediaForArtwork(media, artwork.id);
}

type ComparisonWorkProps = {
  slot: CompareSlot;
  artwork: ArtworkRecord;
  media: MediaAsset[];
  artistName: string;
  locale: Locale;
  lowBandwidth: boolean;
};

function ComparisonWork({
  slot,
  artwork,
  media,
  artistName,
  locale,
  lowBandwidth,
}: ComparisonWorkProps) {
  const copy = galleryCopy[locale];
  const approvedMedia = approvedMediaForArtwork(artwork, media);
  const rightsAsset = approvedMedia.find((asset) => asset.id === artwork.media.representativeMediaId)
    ?? approvedMedia.at(-1)
    ?? null;
  const title = localize(artwork.title, locale);
  const date = artwork.dateDisplay ? localize(artwork.dateDisplay, locale) : "—";
  const institution = artwork.institution ? localize(artwork.institution, locale) : "—";
  const headingId = `compare-${slot}-title`;

  return (
    <article className="compare-work" aria-labelledby={headingId} data-slot={slot}>
      <header className="compare-work-heading">
        <span aria-hidden="true">{slot === "left" ? "01" : "02"}</span>
        <div>
          <p>{artistName}</p>
          <h2 id={headingId}>{title}</h2>
          <p>{date}</p>
        </div>
      </header>

      <ArtworkZoom
        artwork={artwork}
        media={approvedMedia}
        artistName={artistName}
        lowBandwidth={lowBandwidth}
      />

      <section className="compare-metadata" aria-label={`${title} · ${copy.medium}`}>
        <dl>
          <div><dt>{copy.artist}</dt><dd>{artistName}</dd></div>
          <div><dt>{copy.date}</dt><dd>{date}</dd></div>
          <div><dt>{copy.institution}</dt><dd>{institution}</dd></div>
          <div><dt>{copy.accession}</dt><dd>{artwork.accessionNumber ?? "—"}</dd></div>
          <div><dt>{copy.materials}</dt><dd>{localizedList(artwork.materials, locale)}</dd></div>
          <div><dt>{copy.techniques}</dt><dd>{localizedList(artwork.techniques, locale)}</dd></div>
          <div><dt>{copy.subjects}</dt><dd>{localizedList(artwork.subjects, locale)}</dd></div>
          <div><dt>{copy.imageDecision}</dt><dd><code>{artwork.media.decision}</code></dd></div>
        </dl>
      </section>

      <section className="compare-rights" aria-label={`${title} · ${copy.sourceRights}`}>
        {rightsAsset ? (
          <>
            <p><strong>{copy.imageRights}</strong> {rightsAsset.attribution}</p>
            <p>
              <a href={rightsAsset.licenseUrl}>{rightsAsset.licenseIdentifier}</a>
              <span aria-hidden="true"> · </span>
              {rightsAsset.changesStatement}
            </p>
            <p><strong>{copy.withdrawalStatus}</strong> {rightsAsset.withdrawalNotice}</p>
          </>
        ) : (
          <p className="compare-no-image">{copy.noImage}</p>
        )}
        <p><strong>{copy.metadataRule}</strong> <code>{artwork.metadataLicense}</code></p>
        {artwork.objectUrl ? <a className="compare-source-link" href={artwork.objectUrl}>{copy.officialSource}</a> : null}
      </section>
    </article>
  );
}

export function ComparePage({ release, catalog }: GallerySharedProps) {
  const { locale } = useI18n();
  const { compactViewport, forcedColors, lowBandwidth, reducedMotion } = usePreferences();
  const copy = galleryCopy[locale];
  const [searchParams, setSearchParams] = useSearchParams();
  const artworkById = useMemo(
    () => new Map(catalog.artworks.map((artwork) => [artwork.id, artwork])),
    [catalog.artworks],
  );
  const artistById = useMemo(
    () => new Map(release.artists.map((artist) => [artist.id, artist])),
    [release.artists],
  );
  const sortedArtists = useMemo(() => [...release.artists].sort((left, right) =>
    localize(left.labels, locale).localeCompare(localize(right.labels, locale), locale)), [locale, release.artists]);
  const worksByArtist = useMemo(() => {
    const groups = new Map<string, ArtworkRecord[]>();
    for (const artist of sortedArtists) {
      groups.set(artist.id, catalog.artworks
        .filter((artwork) => artwork.artistId === artist.id)
        .sort((left, right) => localize(left.title, locale).localeCompare(localize(right.title, locale), locale)));
    }
    return groups;
  }, [catalog.artworks, locale, sortedArtists]);

  const rawLeftId = searchParams.get("left");
  const rawRightId = searchParams.get("right");
  const leftId = rawLeftId && artworkById.has(rawLeftId) ? rawLeftId : "";
  const rightCandidate = rawRightId && artworkById.has(rawRightId) ? rawRightId : "";
  const rightId = rightCandidate && rightCandidate !== leftId ? rightCandidate : "";
  const leftArtwork = leftId ? artworkById.get(leftId) ?? null : null;
  const rightArtwork = rightId ? artworkById.get(rightId) ?? null : null;

  useEffect(() => {
    const next = new URLSearchParams(searchParams);
    let changed = false;
    if (rawLeftId !== null && rawLeftId !== leftId) {
      next.delete("left");
      changed = true;
    }
    if (rawRightId !== null && rawRightId !== rightId) {
      next.delete("right");
      changed = true;
    }
    if (changed) setSearchParams(next, { replace: true });
  }, [leftId, rawLeftId, rawRightId, rightId, searchParams, setSearchParams]);

  const updateSelection = (slot: CompareSlot, nextId: string) => {
    const next = new URLSearchParams(searchParams);
    const otherId = slot === "left" ? rightId : leftId;
    if (!nextId || nextId === otherId) next.delete(slot);
    else next.set(slot, nextId);
    setSearchParams(next, { replace: true });
  };

  const swapWorks = () => {
    if (!leftArtwork || !rightArtwork) return;
    const next = new URLSearchParams(searchParams);
    next.set("left", rightArtwork.id);
    next.set("right", leftArtwork.id);
    setSearchParams(next, { replace: true });
  };

  const statusText = leftArtwork && rightArtwork
    ? `${copy.compareReady}: ${localize(leftArtwork.title, locale)} / ${localize(rightArtwork.title, locale)}`
    : copy.compareNeedsTwo;

  const options = (otherId: string) => sortedArtists.map((artist) => (
    <optgroup key={artist.id} label={localize(artist.labels, locale)}>
      {(worksByArtist.get(artist.id) ?? []).map((artwork) => (
        <option key={artwork.id} value={artwork.id} disabled={artwork.id === otherId}>
          {localize(artwork.title, locale)}{artwork.dateDisplay ? ` · ${localize(artwork.dateDisplay, locale)}` : ""}
        </option>
      ))}
    </optgroup>
  ));

  return (
    <main
      id="main-content"
      className="inner-page gallery-page compare-page"
      data-compact={compactViewport ? "true" : "false"}
      data-forced-colors={forcedColors ? "active" : "none"}
      data-reduced-motion={reducedMotion ? "true" : "false"}
      tabIndex={-1}
    >
      <nav className="compare-breadcrumbs" aria-label={copy.compareEyebrow}>
        <Link to="/art/artists">{copy.artistIndex}</Link>
        <Link to="/art/constellation">{copy.backConstellation}</Link>
      </nav>

      <header className="compare-hero">
        <p className="eyebrow">{copy.compareEyebrow}</p>
        <h1>{copy.compareTitle}</h1>
        <p>{copy.compareIntro}</p>
      </header>

      <section className="compare-controls" aria-label={copy.compareEyebrow}>
        <label htmlFor="compare-left-select">
          <span>{copy.chooseLeft}</span>
          <select
            id="compare-left-select"
            aria-describedby="compare-selection-status"
            value={leftId}
            onChange={(event) => updateSelection("left", event.currentTarget.value)}
          >
            <option value="">— {copy.chooseLeft} —</option>
            {options(rightId)}
          </select>
        </label>

        <button type="button" className="compare-swap" disabled={!leftArtwork || !rightArtwork} onClick={swapWorks}>
          <span aria-hidden="true">⇄</span>
          {copy.swapWorks}
        </button>

        <label htmlFor="compare-right-select">
          <span>{copy.chooseRight}</span>
          <select
            id="compare-right-select"
            aria-describedby="compare-selection-status"
            value={rightId}
            onChange={(event) => updateSelection("right", event.currentTarget.value)}
          >
            <option value="">— {copy.chooseRight} —</option>
            {options(leftId)}
          </select>
        </label>
      </section>

      <p id="compare-selection-status" className="compare-status" role="status" aria-live="polite" aria-atomic="true">
        {statusText}
      </p>

      {leftArtwork && rightArtwork ? (
        <section className="compare-stage" aria-label={copy.compareReady}>
          <ComparisonWork
            slot="left"
            artwork={leftArtwork}
            media={catalog.media}
            artistName={localize(artistById.get(leftArtwork.artistId)?.labels ?? { "zh-Hans": "—", en: "—" }, locale)}
            locale={locale}
            lowBandwidth={lowBandwidth}
          />
          <ComparisonWork
            slot="right"
            artwork={rightArtwork}
            media={catalog.media}
            artistName={localize(artistById.get(rightArtwork.artistId)?.labels ?? { "zh-Hans": "—", en: "—" }, locale)}
            locale={locale}
            lowBandwidth={lowBandwidth}
          />
        </section>
      ) : (
        <section className="compare-empty" aria-labelledby="compare-empty-title">
          <span aria-hidden="true">⇄</span>
          <h2 id="compare-empty-title">{copy.compareNeedsTwo}</h2>
        </section>
      )}

      <section className="compare-prompts" aria-labelledby="comparison-prompts-title">
        <p className="eyebrow">{copy.comparisonPrompts}</p>
        <h2 id="comparison-prompts-title">{copy.comparisonPrompts}</h2>
        <ol>
          {copy.prompts.map((prompt, index) => (
            <li key={prompt}><span aria-hidden="true">0{index + 1}</span><p>{prompt}</p></li>
          ))}
        </ol>
        <p className="compare-boundary"><strong>{copy.noSimilarity}</strong></p>
      </section>
    </main>
  );
}
