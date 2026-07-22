import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useI18n } from "../../../i18n/I18nProvider";
import { usePreferences } from "../../../preferences/PreferencesProvider";
import {
  localize,
  type ArtworkDetails,
  type EvidenceRecord,
} from "../../art-constellation/types";
import { galleryCopy } from "../copy";
import type { GallerySharedProps } from "../gallery-types";
import { artistPath } from "../media";
import { ArtworkZoom } from "./ArtworkZoom";
import { ObservationCard } from "../observation/ObservationCard";
import { ObservationLenses } from "../observation/ObservationLenses";
import { PrintShareControls } from "../observation/PrintShareControls";
import "./artwork.css";
import "../observation/observation.css";

type DetailState =
  | { requestKey: string; status: "loading" }
  | { requestKey: string; status: "loaded"; data: ArtworkDetails }
  | { requestKey: string; status: "failed" };

export type ArtworkDetailPageProps = GallerySharedProps & { artworkId: string };

function localizedList(values: ArtworkDetails["artwork"]["materials"], locale: "zh-CN" | "en") {
  return values.map((value) => localize(value, locale)).join(locale === "zh-CN" ? "、" : ", ");
}

function sourceIdsForEvidence(evidence: EvidenceRecord[]) {
  return new Set(evidence.flatMap((item) => item.sourceIds));
}

export function ArtworkDetailPage({ release, catalog, dataSource, interactions, artworkId }: ArtworkDetailPageProps) {
  const { locale, t } = useI18n();
  const { lowBandwidth } = usePreferences();
  const copy = galleryCopy[locale];
  const existsInCatalog = catalog.artworks.some((artwork) => artwork.id === artworkId);
  const [attempt, setAttempt] = useState(0);
  const requestKey = `${artworkId}:${attempt}`;
  const [state, setState] = useState<DetailState>({ requestKey, status: "loading" });
  const [searchParams, setSearchParams] = useSearchParams();
  const observationCard = useMemo(
    () => interactions.observation_cards.find((card) => card.artwork_id === artworkId) ?? null,
    [artworkId, interactions.observation_cards],
  );
  const detailRegions = useMemo(
    () => interactions.detail_regions.filter((region) => region.artwork_id === artworkId),
    [artworkId, interactions.detail_regions],
  );
  const requestedRegion = searchParams.get("region");
  const selectedRegion = requestedRegion && detailRegions.some((region) => region.id === requestedRegion) ? requestedRegion : null;
  const printMode = searchParams.get("view") === "print";

  useEffect(() => {
    if (!existsInCatalog) return;
    const controller = new AbortController();
    void dataSource.loadArtworkDetails(artworkId, controller.signal).then((result) => {
      if (controller.signal.aborted) return;
      setState(result.status === "loaded"
        ? { requestKey, status: "loaded", data: result.data }
        : { requestKey, status: "failed" });
    });
    return () => controller.abort();
  }, [artworkId, dataSource, existsInCatalog, requestKey]);

  useEffect(() => {
    const next = new URLSearchParams();
    if (printMode) next.set("view", "print");
    if (selectedRegion) next.set("region", selectedRegion);
    if (next.toString() !== searchParams.toString()) setSearchParams(next, { replace: true });
  }, [printMode, searchParams, selectedRegion, setSearchParams]);

  const visibleState: DetailState = !existsInCatalog
    ? { requestKey, status: "failed" }
    : state.requestKey === requestKey
      ? state
      : { requestKey, status: "loading" };

  if (visibleState.status === "loading") {
    return (
      <main id="main-content" className="artwork-detail-page artwork-detail-state" tabIndex={-1}>
        <p role="status">{copy.loading}</p>
      </main>
    );
  }

  if (visibleState.status === "failed") {
    return (
      <main id="main-content" className="artwork-detail-page artwork-detail-state" tabIndex={-1}>
        <p className="eyebrow">{copy.artworkEyebrow}</p>
        <h1>{copy.artworkNotFound}</h1>
        <p>{copy.loadErrorText}</p>
        {existsInCatalog ? (
          <button type="button" onClick={() => setAttempt((current) => current + 1)}>{t.constellation.retry}</button>
        ) : null}
        <Link className="text-link" to="/art/artists">{copy.artistIndex}</Link>
      </main>
    );
  }

  const { artwork, artist, media, claims, evidence, sources } = visibleState.data;
  const title = localize(artwork.title, locale);
  const artistName = localize(artist.labels, locale);
  const evidenceById = new Map(evidence.map((item) => [item.id, item]));
  const sourceById = new Map(sources.map((source) => [source.id, source]));
  const referencedSourceIds = sourceIdsForEvidence(evidence);
  const details = [
    [copy.artist, <Link to={artistPath(artist.publicSlug)}>{artistName}</Link>],
    [copy.date, artwork.dateDisplay ? localize(artwork.dateDisplay, locale) : "\u2014"],
    [copy.institution, artwork.institution ? localize(artwork.institution, locale) : "\u2014"],
    [copy.accession, artwork.accessionNumber ?? "\u2014"],
    [copy.materials, artwork.materials.length ? localizedList(artwork.materials, locale) : "\u2014"],
    [copy.techniques, artwork.techniques.length ? localizedList(artwork.techniques, locale) : "\u2014"],
    [copy.subjects, artwork.subjects.length ? localizedList(artwork.subjects, locale) : "\u2014"],
  ] as const;
  const compareSearch = new URLSearchParams({ left: artwork.id }).toString();
  return (
    <main
      id="main-content"
      className="artwork-detail-page"
      tabIndex={-1}
      data-artwork-id={artwork.id}
      data-media-decision={artwork.media.decision}
      data-release={release.version}
    >
      <header className="artwork-detail-hero">
        <div>
          <p className="eyebrow">{copy.artworkEyebrow}</p>
          <h1>{title}</h1>
          <p className="artwork-detail-byline">
            <Link to={artistPath(artist.publicSlug)}>{artistName}</Link>
            {artwork.dateDisplay ? <span>{localize(artwork.dateDisplay, locale)}</span> : null}
          </p>
        </div>
        <aside aria-label={copy.imageDecision}>
          <span>{copy.imageDecision}</span>
          <strong>{artwork.media.decision === "approved_self_hosted" ? (locale === "zh-CN" ? "本站图像" : "Image available here") : artwork.media.decision === "external_link_only" ? (locale === "zh-CN" ? "仅链接官方对象页" : "Official object page only") : (locale === "zh-CN" ? "元数据优先" : "Metadata first")}</strong>
          <small>{artwork.media.decision === "external_link_only" ? (locale === "zh-CN" ? "本站不托管或请求该作品图像。" : "This site does not host or request an image for this work.") : artwork.media.decision === "metadata_only" ? (locale === "zh-CN" ? "完整元数据与来源仍可查阅。" : "Complete metadata and sources remain available.") : (locale === "zh-CN" ? "已发布的本站衍生图像。" : "Published site-hosted derivative image.")}</small>
        </aside>
      </header>

      <div className="artwork-detail-layout">
        <ArtworkZoom
          artwork={artwork}
          media={media}
          artistName={artistName}
          lowBandwidth={lowBandwidth}
          regions={detailRegions}
          activeRegionId={selectedRegion}
          onRegionChange={(regionId) => {
            const next = new URLSearchParams();
            if (printMode) next.set("view", "print");
            if (regionId) next.set("region", regionId);
            setSearchParams(next, { replace: true });
          }}
          printMode={printMode}
        />

        <aside className="artwork-object-record" aria-labelledby="artwork-object-record-title">
          <p className="eyebrow">{copy.medium}</p>
          <h2 id="artwork-object-record-title">{title}</h2>
          <dl>
            {details.map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
          <div className="artwork-original-title">
            <h3>{copy.originalTitle}</h3>
            <p>{copy.originalTitleUnavailable}</p>
          </div>
          {artwork.mediumDisplay ? <p className="artwork-medium-display">{localize(artwork.mediumDisplay, locale)}</p> : null}
          {artwork.limitations ? (
            <div className="artwork-limitations">
              <h3>{copy.limitations}</h3>
              <p>{localize(artwork.limitations, locale)}</p>
            </div>
          ) : null}
          <p><strong>{copy.metadataRule}</strong><br />{artwork.metadataLicense}</p>
          {artwork.attribution ? <p>{artwork.attribution}</p> : null}
          {artwork.objectUrl ? (
            <a className="artwork-official-link" href={artwork.objectUrl} rel="noreferrer">
              {copy.officialSource}
            </a>
          ) : null}
        </aside>
      </div>

      {observationCard ? <ObservationCard card={observationCard} /> : (
        <section className="artwork-observation-card" aria-labelledby="metadata-observation-title">
          <p className="eyebrow">{locale === "zh-CN" ? "元数据观察路径" : "Metadata observation path"}</p>
          <h2 id="metadata-observation-title">{locale === "zh-CN" ? "从对象记录开始" : "Begin with the object record"}</h2>
          <p>{locale === "zh-CN" ? "比较标题、年代、材料与收藏机构；来源未提供的信息保持为空，不从图像缺失推断作品意义。" : "Compare title, date, material, and holding institution. Missing source fields remain empty, and no meaning is inferred from an unavailable image."}</p>
        </section>
      )}
      <ObservationLenses lenses={interactions.lenses} artworkIds={[artwork.id]} />

      <section className="artwork-evidence" aria-labelledby="artwork-evidence-title">
        <div className="artwork-section-heading">
          <p className="eyebrow">{"Claim \u2192 Evidence \u2192 Source"}</p>
          <h2 id="artwork-evidence-title">{copy.evidence}</h2>
        </div>
        <ol className="artwork-claim-list">
          {claims.map((claim, claimIndex) => {
            const claimEvidence = claim.evidenceIds
              .map((evidenceId) => evidenceById.get(evidenceId))
              .filter((item): item is EvidenceRecord => Boolean(item));
            return (
              <li key={claim.id}>
                <p className="artwork-record-id">{locale === "zh-CN" ? `作品论断 ${claimIndex + 1}` : `Artwork claim ${claimIndex + 1}`}</p>
                <h3>{localize(claim.text, locale)}</h3>
                <p className="artwork-predicate">{locale === "zh-CN" ? "馆藏记录中的作品身份" : "Object identity in the collection record"}</p>
                <ul aria-label={copy.evidenceRecords}>
                  {claimEvidence.map((item) => (
                    <li key={item.id}>
                      <p>{localize(item.summary, locale)}</p>
                      <p className="artwork-evidence-note">{localize(item.reliabilityNote, locale)}</p>
                      {item.locator ? <p className="artwork-record-id">{item.locator}</p> : null}
                      <ul className="artwork-evidence-source-links" aria-label={copy.sourceRights}>
                        {item.sourceIds.map((sourceId) => {
                          const source = sourceById.get(sourceId);
                          return source ? <li key={sourceId}><a href={source.officialUrl} rel="noreferrer">{source.title}</a></li> : null;
                        })}
                      </ul>
                    </li>
                  ))}
                </ul>
              </li>
            );
          })}
        </ol>

        <div className="artwork-source-list">
          <h3>{copy.sourceRights}</h3>
          <ul>
            {sources.map((source) => (
              <li key={source.id} data-evidence-source={referencedSourceIds.has(source.id) ? "true" : "artwork-metadata"}>
                <a href={source.officialUrl} rel="noreferrer">{source.title}</a>
                <p>{source.publisher}{source.date ? ` \u00b7 ${source.date}` : ""}</p>
                <p>{source.license}<span aria-hidden="true"> &middot; </span>{source.attribution}</p>
                {source.locator ? <p>{localize(source.locator, locale)}</p> : null}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <PrintShareControls
        releaseId={release.manifestId}
        releaseVersion={release.version}
        state={{ region: selectedRegion }}
      />

      <nav className="artwork-detail-actions" aria-label={copy.artworkEyebrow}>
        <Link className="text-link" to={artistPath(artist.publicSlug)}>{copy.artistGalleryEyebrow}</Link>
        <Link className="text-link" to={`/art/compare?${compareSearch}`}>{copy.compareLink}</Link>
        <Link className="text-link" to={`/art/paths?from=${encodeURIComponent(artist.id)}&to=${encodeURIComponent(release.artists.find((candidate) => candidate.id !== artist.id)?.id ?? "")}&mode=comparison&maxHops=6&path=1&view=text`}>
          {locale === "zh-CN" ? "艺术家关系路径" : "Artist pathways"}
        </Link>
        <Link className="text-link" to="/art/constellation">{copy.backConstellation}</Link>
        <Link className="text-link" to={`/art/map?artist=${encodeURIComponent(artist.id)}&view=list`}>{locale === "zh-CN" ? "艺术家地点与当前馆藏" : "Artist places and current holding"}</Link>
      </nav>
    </main>
  );
}
