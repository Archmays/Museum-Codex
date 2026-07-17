import { useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArtworkImage } from "../../art-constellation/ArtworkImage";
import { localize } from "../../art-constellation/types";
import { useI18n } from "../../../i18n/I18nProvider";
import { usePreferences } from "../../../preferences/PreferencesProvider";
import type { GallerySharedProps } from "../gallery-types";
import type { ArtistTour, ThematicTour } from "../interaction-types";
import { artworkPath, factualArtworkAlt } from "../media";
import { ObservationCard } from "../observation/ObservationCard";
import { PrintShareControls } from "../observation/PrintShareControls";
import "../observation/observation.css";
import "./tours.css";

type ToursPageProps = GallerySharedProps & { tourId: string | null };

export function ToursPage(props: ToursPageProps) {
  const { tourId } = props;
  const [searchParams, setSearchParams] = useSearchParams();
  useEffect(() => {
    const next = new URLSearchParams();
    if (searchParams.get("view") === "print") next.set("view", "print");
    if (next.toString() !== searchParams.toString()) setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);
  const allTours = [...props.interactions.artist_tours, ...props.interactions.thematic_tours];
  const tour = tourId ? allTours.find((entry) => entry.id === tourId) ?? null : null;
  if (tourId && !tour) return <InvalidTour />;
  return tour ? <TourDetail {...props} tour={tour} /> : <TourIndex {...props} />;
}

function TourIndex({ release, interactions }: GallerySharedProps) {
  const { locale } = useI18n();
  const zh = locale === "zh-CN";
  return (
    <main id="main-content" className="gallery-page tours-page" tabIndex={-1}>
      <nav className="tour-breadcrumbs" aria-label={zh ? "导览导航" : "Tour navigation"}>
        <Link to="/art">{zh ? "美术馆序厅" : "Art foyer"}</Link>
        <Link to="/art/compare">{zh ? "双作比较" : "Two-work comparison"}</Link>
        <Link to="/art/map">{zh ? "艺术时空地图" : "Art Across Time and Place"}</Link>
      </nav>
      <header className="tours-hero">
        <p className="eyebrow">{zh ? "深度观察导览" : "Deep observation tours"}</p>
        <h1>{zh ? "十八条固定路线，慢下来观看" : "Eighteen fixed routes for slower looking"}</h1>
        <p>{zh ? "十二条艺术家导览与六条主题导览都由正式作品、经审核语境与来源组成。它们不是自动推荐，也不搜索任意关系路径。" : "Twelve artist tours and six thematic tours use formal works, reviewed contexts, and sources. They are not automatic recommendations and do not search arbitrary relationship paths."}</p>
        <dl><div><dt>{zh ? "艺术家导览" : "Artist tours"}</dt><dd>12</dd></div><div><dt>{zh ? "主题导览" : "Thematic tours"}</dt><dd>6</dd></div><div><dt>{zh ? "发布" : "Release"}</dt><dd>{release.version}</dd></div></dl>
      </header>

      <section className="tour-index-section" aria-labelledby="artist-tour-index-title">
        <p className="eyebrow">01</p><h2 id="artist-tour-index-title">{zh ? "十二位艺术家的观察入口" : "Observation entries for twelve artists"}</h2>
        <ol className="tour-index-grid">
          {interactions.artist_tours.map((tour) => (
            <li key={tour.id}><article><p>{localize(tour.focus.label, locale)}</p><h3>{localize(tour.title, locale)}</h3><p>{localize(tour.entry_question, locale)}</p><Link to={`/art/tours/${encodeURIComponent(tour.id)}`}>{zh ? "进入导览" : "Enter tour"}</Link></article></li>
          ))}
        </ol>
      </section>

      <section className="tour-index-section" aria-labelledby="theme-tour-index-title">
        <p className="eyebrow">02</p><h2 id="theme-tour-index-title">{zh ? "六条主题策展导览" : "Six thematic curatorial tours"}</h2>
        <ol className="tour-index-grid tour-theme-grid">
          {interactions.thematic_tours.map((tour) => (
            <li key={tour.id}><article><p>{tour.artist_ids.length} {zh ? "位艺术家" : "artists"} · {tour.artwork_ids.length} {zh ? "件作品" : "works"}</p><h3>{localize(tour.title, locale)}</h3><p>{localize(tour.summary, locale)}</p><Link to={`/art/tours/${encodeURIComponent(tour.id)}`}>{zh ? "进入固定导览" : "Enter fixed tour"}</Link></article></li>
          ))}
        </ol>
      </section>
    </main>
  );
}

function TourDetail({ release, catalog, interactions, tour }: GallerySharedProps & { tour: ArtistTour | ThematicTour }) {
  const { locale } = useI18n();
  const { lowBandwidth } = usePreferences();
  const zh = locale === "zh-CN";
  const artistTour = tour.kind === "artist" ? tour : null;
  const themeTour = tour.kind === "thematic" ? tour : null;
  const artworkIds = artistTour ? artistTour.artwork_steps.map((step) => step.artwork_id) : themeTour!.artwork_ids;
  const reasonByArtwork = new Map(artistTour?.artwork_steps.map((step) => [step.artwork_id, step.reason]) ?? []);
  const artworks = artworkIds.map((id) => catalog.artworks.find((item) => item.id === id)).filter((item) => item !== undefined);
  const artistById = new Map(release.artists.map((artist) => [artist.id, artist]));
  const imageArtwork = artworks.find((artwork) => artwork.media.decision === "approved_self_hosted") ?? artworks[0] ?? null;
  return (
    <main id="main-content" className="gallery-page tour-detail-page" tabIndex={-1} data-tour-id={tour.id}>
      <nav className="tour-breadcrumbs" aria-label={zh ? "导览导航" : "Tour navigation"}><Link to="/art/tours">← {zh ? "全部导览" : "All tours"}</Link><Link to="/art/compare">{zh ? "双作比较" : "Compare"}</Link><Link to="/art/map">{zh ? "艺术时空地图" : "Art Across Time and Place"}</Link></nav>
      <header className="tour-detail-hero">
        <p className="eyebrow">{artistTour ? (zh ? "艺术家观察导览" : "Artist observation tour") : (zh ? "主题策展导览" : "Thematic curatorial tour")}</p>
        <h1>{localize(tour.title, locale)}</h1>
        <p>{artistTour ? localize(artistTour.entry_question, locale) : localize(themeTour!.summary, locale)}</p>
        <p className="tour-fixed-boundary">{artistTour ? localize(artistTour.disclaimer, locale) : localize(themeTour!.noncausal_statement, locale)}</p>
      </header>

      {imageArtwork ? (
        <section className="tour-single-image" aria-label={zh ? "导览小图" : "Tour thumbnail"}>
          <ArtworkImage
            artworkId={imageArtwork.id}
            representativeMediaId={imageArtwork.media.representativeMediaId}
            media={catalog.media}
            alt={factualArtworkAlt(localize(artistById.get(imageArtwork.artistId)?.labels ?? { "zh-Hans": "—", en: "—" }, locale), imageArtwork, imageArtwork.dateDisplay ? localize(imageArtwork.dateDisplay, locale) : null, locale)}
            lowBandwidth={lowBandwidth}
            variant="thumbnail"
            noImageText={zh ? "此导览使用无图元数据路径。" : "This tour uses the no-image metadata path."}
            lowBandwidthText={zh ? "低带宽模式默认不请求导览图像。" : "Low-bandwidth mode makes no tour image request by default."}
            loadImageText={zh ? "加载这张小图" : "Load this thumbnail"}
            imageLoadingText={zh ? "正在加载导览小图。" : "Loading tour thumbnail."}
            imageLoadedText={zh ? "导览小图已加载。" : "Tour thumbnail loaded."}
            unavailableText={zh ? "小图不可用，元数据路径仍完整。" : "Thumbnail unavailable; the metadata path remains complete."}
            rightsLabel={zh ? "媒体署名与许可：" : "Media attribution and license:"}
            withdrawalLabel={zh ? "撤回状态：" : "Withdrawal status:"}
            officialSourceLabel={zh ? "官方作品来源" : "Official object source"}
            officialSourceUrl={imageArtwork.objectUrl}
          />
        </section>
      ) : null}

      {artistTour ? <ArtistTourGuide tour={artistTour} locale={locale} /> : <ThemeTourGuide tour={themeTour!} locale={locale} />}

      <section className="tour-work-list" aria-labelledby="tour-work-list-title">
        <p className="eyebrow">{zh ? "作品顺序" : "Work sequence"}</p><h2 id="tour-work-list-title">{zh ? "沿记录逐件观察" : "Observe one formal record at a time"}</h2>
        <ol>
          {artworks.map((artwork, index) => {
            const card = interactions.observation_cards.find((item) => item.artwork_id === artwork.id);
            return (
              <li key={artwork.id}>
                <article>
                  <span aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
                  <div>
                    <p>{localize(artistById.get(artwork.artistId)?.labels ?? { "zh-Hans": "—", en: "—" }, locale)}</p>
                    <h3><Link to={artworkPath(artwork.id)}>{localize(artwork.title, locale)}</Link></h3>
                    <p>{artwork.media.decision === "approved_self_hosted" ? (zh ? "批准图像与文字路径" : "Approved image and text path") : (zh ? "完整元数据与证据路径" : "Complete metadata and evidence path")}</p>
                    {reasonByArtwork.get(artwork.id) ? <p className="tour-step-reason">{localize(reasonByArtwork.get(artwork.id)!, locale)}</p> : null}
                  </div>
                </article>
                {card ? <details><summary>{zh ? "展开观察卡" : "Open observation card"}</summary><ObservationCard card={card} compact headingLevel={4} /></details> : null}
              </li>
            );
          })}
        </ol>
      </section>

      <section className="tour-source-boundary"><h2>{zh ? "来源与路径边界" : "Sources and path boundary"}</h2><p>{tour.source_ids.join(" · ")}</p><p>{zh ? "无图作品使用同一组观察问题、完整元数据、证据和来源，不布置肉眼细节任务。" : "Works without images use the same observation questions, complete metadata, evidence, and sources; no visual-detail task is assigned."}</p></section>
      <PrintShareControls releaseId={release.manifestId} releaseVersion={release.version} />
      <nav className="tour-end-paths" aria-label={zh ? "导览结束后的路径入口" : "Pathway entry after the tour"}>
        <Link to={`/art/paths?from=${encodeURIComponent((artistTour ? [artistTour.artist_id] : themeTour!.artist_ids)[0])}&to=${encodeURIComponent((artistTour ? release.artists.map((artist) => artist.id).filter((id) => id !== artistTour.artist_id) : themeTour!.artist_ids.slice(1))[0])}&mode=comparison&maxHops=6&path=1&view=text`}>
          {zh ? "导览结束：继续查看艺术家关系路径" : "Tour complete: continue to artist pathways"}
        </Link>
        <Link to={`/art/map?artist=${encodeURIComponent((artistTour ? [artistTour.artist_id] : themeTour!.artist_ids)[0])}&view=timeline`}>{zh ? "在地点时间线中继续" : "Continue in the place timeline"}</Link>
      </nav>
    </main>
  );
}

function ArtistTourGuide({ tour, locale }: { tour: ArtistTour; locale: "zh-CN" | "en" }) {
  const rows = [tour.time_place_context, tour.evidence_check, tour.do_not_overinterpret, tour.reflection_question];
  return <section className="tour-guide"><h2>{locale === "zh-CN" ? "导览线索" : "Tour cues"}</h2><ol>{rows.map((row, index) => <li key={index}><span aria-hidden="true">{index + 1}</span><p>{localize(row, locale)}</p></li>)}</ol><div className="tour-equivalent-paths"><p>{localize(tour.equivalent_paths.image, locale)}</p><p>{localize(tour.equivalent_paths.no_image, locale)}</p></div></section>;
}

function ThemeTourGuide({ tour, locale }: { tour: ThematicTour; locale: "zh-CN" | "en" }) {
  return <section className="tour-guide"><h2>{locale === "zh-CN" ? "经审核语境" : "Reviewed contexts"}</h2><p>{tour.period_labels.map((label) => localize(label, locale)).join(" · ")}</p><p>{tour.region_labels.map((label) => localize(label, locale)).join(" · ")}</p><p>{tour.context_ids.join(" · ")}</p><p>{localize(tour.noncausal_statement, locale)}</p></section>;
}

function InvalidTour() {
  const { locale } = useI18n();
  return <main id="main-content" className="gallery-page gallery-empty-state" tabIndex={-1}><span aria-hidden="true">∅</span><div><h1>{locale === "zh-CN" ? "没有找到这条正式导览" : "This formal tour was not found"}</h1><p>{locale === "zh-CN" ? "导览 ID 无效或不在当前发布中。" : "The tour ID is invalid or is not in the current release."}</p><Link to="/art/tours">{locale === "zh-CN" ? "返回全部导览" : "Back to all tours"}</Link></div></main>;
}

export default ToursPage;
