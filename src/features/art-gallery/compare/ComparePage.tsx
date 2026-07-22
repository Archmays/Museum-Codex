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
import { ObservationCard } from "../observation/ObservationCard";
import { ObservationLenses } from "../observation/ObservationLenses";
import { PrintShareControls } from "../observation/PrintShareControls";
import { galleryCopy } from "../copy";
import type { GallerySharedProps } from "../gallery-types";
import type { DetailRegion, ObservationCard as ObservationCardRecord } from "../interaction-types";
import { mediaForArtwork } from "../media";
import "../artwork/artwork.css";
import "../observation/observation.css";
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
  card: ObservationCardRecord | null;
  regions: DetailRegion[];
  activeRegionId: string | null;
  onRegionChange: (regionId: string | null) => void;
  printMode: boolean;
};

function ComparisonWork({
  slot,
  artwork,
  media,
  artistName,
  locale,
  lowBandwidth,
  card,
  regions,
  activeRegionId,
  onRegionChange,
  printMode,
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
        regions={regions}
        activeRegionId={activeRegionId}
        onRegionChange={onRegionChange}
        printMode={printMode}
      />

      {card ? <ObservationCard card={card} compact headingLevel={3} /> : (
        <section className="compare-metadata-observation" aria-label={locale === "zh-CN" ? "元数据观察路径" : "Metadata observation path"}>
          <h3>{locale === "zh-CN" ? "从对象记录开始" : "Begin with the object record"}</h3>
          <p>{locale === "zh-CN" ? "比较标题、年代、材料与收藏机构；图像缺失不用于推断作品意义或价值。" : "Compare title, date, materials, and holding institution; image availability is never used to infer meaning or value."}</p>
        </section>
      )}

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

export function ComparePage({ release, catalog, interactions }: GallerySharedProps) {
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
  const rawLens = searchParams.get("lens");
  const lens = rawLens && ["material", "technique", "subject"].includes(rawLens) ? rawLens : null;
  const printMode = searchParams.get("view") === "print";
  const regionsFor = (artworkId: string) => interactions.detail_regions.filter((region) => region.artwork_id === artworkId);
  const leftRegions = leftArtwork ? regionsFor(leftArtwork.id) : [];
  const rightRegions = rightArtwork ? regionsFor(rightArtwork.id) : [];
  const rawLeftRegion = searchParams.get("leftRegion");
  const rawRightRegion = searchParams.get("rightRegion");
  const leftRegion = rawLeftRegion && leftRegions.some((region) => region.id === rawLeftRegion) ? rawLeftRegion : null;
  const rightRegion = rawRightRegion && rightRegions.some((region) => region.id === rawRightRegion) ? rawRightRegion : null;

  const writeState = (nextState: {
    left?: string | null;
    right?: string | null;
    lens?: string | null;
    leftRegion?: string | null;
    rightRegion?: string | null;
    view?: string | null;
  }) => {
    const next = new URLSearchParams();
    const merged = {
      left: leftId,
      right: rightId,
      lens,
      leftRegion,
      rightRegion,
      view: printMode ? "print" : null,
      ...nextState,
    };
    for (const key of ["left", "right", "lens", "leftRegion", "rightRegion", "view"] as const) {
      const value = merged[key];
      if (value) next.set(key, value);
    }
    setSearchParams(next, { replace: true });
  };

  useEffect(() => {
    const next = new URLSearchParams();
    if (leftId) next.set("left", leftId);
    if (rightId) next.set("right", rightId);
    if (lens) next.set("lens", lens);
    if (leftRegion) next.set("leftRegion", leftRegion);
    if (rightRegion) next.set("rightRegion", rightRegion);
    if (printMode) next.set("view", "print");
    if (next.toString() !== searchParams.toString()) setSearchParams(next, { replace: true });
  }, [leftId, leftRegion, lens, printMode, rightId, rightRegion, searchParams, setSearchParams]);

  const updateSelection = (slot: CompareSlot, nextId: string) => {
    const otherId = slot === "left" ? rightId : leftId;
    writeState({ [slot]: !nextId || nextId === otherId ? null : nextId, [slot === "left" ? "leftRegion" : "rightRegion"]: null });
  };

  const swapWorks = () => {
    if (!leftArtwork || !rightArtwork) return;
    writeState({ left: rightArtwork.id, right: leftArtwork.id, leftRegion: rightRegion, rightRegion: leftRegion });
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
        <button type="button" className="compare-clear" disabled={!leftArtwork && !rightArtwork} onClick={() => setSearchParams(new URLSearchParams(), { replace: true })}>
          {locale === "zh-CN" ? "清除比较" : "Clear comparison"}
        </button>
      </section>

      <p id="compare-selection-status" className="compare-status" role="status" aria-live="polite" aria-atomic="true">
        {statusText}
      </p>

      {leftArtwork && rightArtwork ? (
        <>
        <SharedDifferentFields left={leftArtwork} right={rightArtwork} locale={locale} />
        <section className="compare-stage" aria-label={copy.compareReady}>
          <ComparisonWork
            slot="left"
            artwork={leftArtwork}
            media={catalog.media}
            artistName={localize(artistById.get(leftArtwork.artistId)?.labels ?? { "zh-Hans": "—", en: "—" }, locale)}
            locale={locale}
            lowBandwidth={lowBandwidth}
            card={interactions.observation_cards.find((card) => card.artwork_id === leftArtwork.id) ?? null}
            regions={leftRegions}
            activeRegionId={leftRegion}
            onRegionChange={(regionId) => writeState({ leftRegion: regionId })}
            printMode={printMode}
          />
          <ComparisonWork
            slot="right"
            artwork={rightArtwork}
            media={catalog.media}
            artistName={localize(artistById.get(rightArtwork.artistId)?.labels ?? { "zh-Hans": "—", en: "—" }, locale)}
            locale={locale}
            lowBandwidth={lowBandwidth}
            card={interactions.observation_cards.find((card) => card.artwork_id === rightArtwork.id) ?? null}
            regions={rightRegions}
            activeRegionId={rightRegion}
            onRegionChange={(regionId) => writeState({ rightRegion: regionId })}
            printMode={printMode}
          />
        </section>
        <ObservationLenses
          lenses={interactions.lenses}
          artworkIds={[leftArtwork.id, rightArtwork.id]}
          activeLens={lens as "material" | "technique" | "subject" | null}
          onLensChange={(nextLens) => writeState({ lens: nextLens })}
        />
        <PrintShareControls
          releaseId={release.manifestId}
          releaseVersion={release.version}
          state={{ left: leftId, right: rightId, lens, leftRegion, rightRegion }}
        />
        {leftArtwork.artistId !== rightArtwork.artistId ? (
          <Link className="compare-path-entry" to={`/art/paths?from=${encodeURIComponent(leftArtwork.artistId)}&to=${encodeURIComponent(rightArtwork.artistId)}&mode=comparison&maxHops=6&path=1&view=text`}>
            {locale === "zh-CN" ? "查看这两位艺术家的可解释关系路径" : "View an explainable path between these artists"}
          </Link>
        ) : null}
        </>
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
          {interactions.compare_prompts.map((prompt, index) => (
            <li key={prompt.id}><span aria-hidden="true">0{index + 1}</span><p>{localize(prompt.prompt, locale)}</p></li>
          ))}
        </ol>
        <p className="compare-boundary"><strong>{copy.noSimilarity}</strong><br />{localize(interactions.compare_prompts[0]?.boundary ?? { "zh-Hans": copy.noSimilarity, en: copy.noSimilarity }, locale)}</p>
      </section>
    </main>
  );
}

function SharedDifferentFields({ left, right, locale }: { left: ArtworkRecord; right: ArtworkRecord; locale: Locale }) {
  const groups = [
    [locale === "zh-CN" ? "材料" : "Materials", left.materials, right.materials],
    [locale === "zh-CN" ? "技法" : "Techniques", left.techniques, right.techniques],
    [locale === "zh-CN" ? "题材" : "Subjects", left.subjects, right.subjects],
  ] as const;
  return (
    <section className="compare-fields" aria-labelledby="compare-fields-title">
      <h2 id="compare-fields-title">{locale === "zh-CN" ? "共同与不同字段" : "Shared and different fields"}</h2>
      <div>{groups.map(([label, leftValues, rightValues]) => {
        const leftLabels = leftValues.map((value) => localize(value, locale));
        const rightLabels = rightValues.map((value) => localize(value, locale));
        const shared = leftLabels.filter((value) => rightLabels.includes(value));
        return <article key={label}><h3>{label}</h3><p><strong>{locale === "zh-CN" ? "共同" : "Shared"}:</strong> {shared.join(" · ") || "—"}</p><p><strong>{locale === "zh-CN" ? "左侧不同" : "Left only"}:</strong> {leftLabels.filter((value) => !shared.includes(value)).join(" · ") || "—"}</p><p><strong>{locale === "zh-CN" ? "右侧不同" : "Right only"}:</strong> {rightLabels.filter((value) => !shared.includes(value)).join(" · ") || "—"}</p></article>;
      })}</div>
    </section>
  );
}
