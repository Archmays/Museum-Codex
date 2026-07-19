import { forwardRef, lazy, Suspense, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useI18n } from "../../i18n/I18nProvider";
import { usePreferences } from "../../preferences/PreferencesProvider";
import { loadMapBundle } from "./map-loader";
import type {
  ArtistEpisode,
  HoldingLocation,
  LocalizedText,
  MapBundle,
  MapFeature,
  MapFilters,
  MapLayer,
  MapView,
  PlaceIdentity,
} from "./types";
import "./art-map.css";

const MapCanvas = lazy(() => import("./MapCanvas").then((module) => ({ default: module.MapCanvas })));
const ALLOWED_VIEWS = new Set(["map", "timeline", "list"]);
const ALLOWED_LAYERS = new Set(["artist_activity", "artwork_creation_place", "current_holding_institution"]);

const episodeLabels: Record<string, [string, string]> = {
  birth: ["出生", "Birth"], death: ["逝世", "Death"], residence: ["居住", "Residence"],
  documented_activity: ["有文献活动", "Documented activity"], training: ["学习", "Training"],
  employment: ["任职", "Employment"], studio: ["工作室", "Studio"], documented_travel: ["有文献旅行", "Documented travel"],
};
const precisionLabels: Record<string, [string, string]> = {
  exact_site: ["确切地点", "Exact site"], locality: ["地方", "Locality"], city_centroid: ["城市中心点", "City centroid"],
  regional_centroid: ["区域中心点", "Regional centroid"], bounded_area: ["有界区域", "Bounded area"], unknown: ["坐标未知，仅列表", "Unknown; list only"],
};
const layerLabels: Record<MapLayer, [string, string]> = {
  artist_activity: ["艺术家生活与活动", "Artist life and activity"],
  artwork_creation_place: ["作品创作地点", "Artwork creation place"],
  current_holding_institution: ["当前馆藏机构", "Current holding institution"],
};

function localize(locale: "zh-CN" | "en", value: LocalizedText) {
  return locale === "zh-CN" ? value["zh-Hans"] : value.en;
}

function yearText(episode: ArtistEpisode) {
  if (episode.start_year === null && episode.end_year === null) return "—";
  if (episode.start_year === episode.end_year || episode.end_year === null) return String(episode.start_year);
  return `${episode.start_year ?? "?"}–${episode.end_year}`;
}

function safeYear(value: string | null, fallback: number, min: number, max: number) {
  if (value === null || value.trim() === "") return fallback;
  const parsed = Number(value);
  return Number.isInteger(parsed) ? Math.min(max, Math.max(min, parsed)) : fallback;
}

function selectedId(value: string | null, bundle: MapBundle) {
  return bundle.episodes.some((item) => item.id === value) || bundle.holdings.some((item) => item.id === value) ? (value ?? "") : "";
}

function sanitizeSearchParams(current: URLSearchParams, bundle: MapBundle) {
  const next = new URLSearchParams();
  const copyIf = (key: string, valid: (value: string) => boolean) => {
    const value = current.get(key);
    if (value && valid(value)) next.set(key, value);
  };
  copyIf("artist", (value) => bundle.artists.some((item) => item.id === value));
  copyIf("place", (value) => bundle.places.some((item) => item.id === value));
  copyIf("episodeType", (value) => bundle.episodes.some((item) => item.episode_type === value));
  for (const key of ["fromYear", "toYear"]) {
    const value = current.get(key);
    if (value !== null && value.trim() !== "") {
      const parsed = Number(value);
      if (Number.isInteger(parsed)) next.set(key, String(Math.min(bundle.mapIndex.year_range.max, Math.max(bundle.mapIndex.year_range.min, parsed))));
    }
  }
  copyIf("region", (value) => bundle.places.some((item) => item.region === value));
  copyIf("precision", (value) => bundle.places.some((item) => item.coordinate_precision === value));
  copyIf("layer", (value) => ALLOWED_LAYERS.has(value));
  copyIf("view", (value) => ALLOWED_VIEWS.has(value));
  copyIf("episode", (value) => selectedId(value, bundle) === value);
  return next;
}

export function ArtMapPage() {
  const { locale } = useI18n();
  const { lowBandwidth, forcedColors, reducedMotion } = usePreferences();
  const [searchParams, setSearchParams] = useSearchParams();
  const [bundle, setBundle] = useState<MapBundle | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [liveMessage, setLiveMessage] = useState("");
  const selectedPanelRef = useRef<HTMLElement>(null);

  useEffect(() => {
    let active = true;
    loadMapBundle().then((result) => { if (active) setBundle(result); }).catch(() => { if (active) setLoadFailed(true); });
    return () => { active = false; };
  }, []);

  const updateState = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(searchParams);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    setSearchParams(next, { replace: true });
  };

  const view = (ALLOWED_VIEWS.has(searchParams.get("view") ?? "") ? searchParams.get("view") : "map") as MapView;
  const effectiveView: MapView = (lowBandwidth || forcedColors) && view === "map" ? "list" : view;

  useEffect(() => {
    if (searchParams.get("episode")) selectedPanelRef.current?.focus();
  }, [searchParams]);

  useEffect(() => {
    if (!bundle) return;
    const sanitized = sanitizeSearchParams(searchParams, bundle);
    if (sanitized.toString() !== searchParams.toString()) setSearchParams(sanitized, { replace: true });
  }, [bundle, searchParams, setSearchParams]);

  if (loadFailed) return <MapUnavailable locale={locale} />;
  if (!bundle) return <main id="main-content" className="art-map-page art-map-page--loading" tabIndex={-1} aria-busy="true">
    <header className="map-hero">
      <div><p className="eyebrow">{locale === "zh-CN" ? "来源支持的地点主张" : "Source-supported place claims"}</p><p className="map-loading-title" aria-hidden="true">{locale === "zh-CN" ? "艺术时空地图" : "Art Across Time and Place"}</p><p className="map-dek">{locale === "zh-CN" ? "沿来源支持的地点主张阅读艺术家的生命与活动；地图、时间线和地点表使用同一状态，不把时间顺序画成旅行路线。" : "Read artists’ lives and activity through source-supported place claims. Map, timeline, and place table share one state and never turn chronology into a travel route."}</p></div>
      <div className="map-release-stamp" aria-hidden="true"><span>— / — / —</span><small>{locale === "zh-CN" ? "艺术家 · 地点 · episodes" : "artists · places · episodes"}</small><b>{locale === "zh-CN" ? "正在核验" : "VERIFYING"}</b></div>
    </header>
    <div className="map-loading-filters" aria-hidden="true" />
    <div className="map-loading-toolbar" aria-hidden="true" />
    <div className="map-loading-workspace" aria-hidden="true" />
    <p role="status" className="sr-only">{locale === "zh-CN" ? "正在核验地图 release……" : "Verifying the map release…"}</p>
  </main>;

  const minYear = bundle.mapIndex.year_range.min;
  const maxYear = bundle.mapIndex.year_range.max;
  const layer = (ALLOWED_LAYERS.has(searchParams.get("layer") ?? "") ? searchParams.get("layer") : "artist_activity") as MapLayer;
  const fromYear = safeYear(searchParams.get("fromYear"), minYear, minYear, maxYear);
  const toYear = safeYear(searchParams.get("toYear"), maxYear, minYear, maxYear);
  const filters: MapFilters = {
    artist: bundle.artists.some((item) => item.id === searchParams.get("artist")) ? searchParams.get("artist")! : "",
    place: bundle.places.some((item) => item.id === searchParams.get("place")) ? searchParams.get("place")! : "",
    episodeType: bundle.episodes.some((item) => item.episode_type === searchParams.get("episodeType")) ? searchParams.get("episodeType")! : "",
    fromYear: Math.min(fromYear, toYear), toYear: Math.max(fromYear, toYear),
    region: bundle.places.some((item) => item.region === searchParams.get("region")) ? searchParams.get("region")! : "",
    precision: bundle.places.some((item) => item.coordinate_precision === searchParams.get("precision")) ? searchParams.get("precision")! : "",
    layer,
  };
  const placeById = new Map(bundle.places.map((place) => [place.id, place]));
  const artistById = new Map(bundle.artists.map((artist) => [artist.id, artist]));
  const artworkById = new Map(bundle.artworks.map((artwork) => [artwork.id, artwork]));
  const sourceById = new Map(bundle.sources.map((source) => [source.id, source]));
  const filteredEpisodes = bundle.episodes.filter((episode) => {
    const place = placeById.get(episode.place_id)!;
    return layer === "artist_activity" && (!filters.artist || episode.artist_id === filters.artist) &&
      (!filters.place || episode.place_id === filters.place) && (!filters.episodeType || episode.episode_type === filters.episodeType) &&
      (!filters.region || place.region === filters.region) && (!filters.precision || episode.place_precision === filters.precision) &&
      (episode.end_year ?? episode.start_year ?? filters.toYear) >= filters.fromYear &&
      (episode.start_year ?? episode.end_year ?? filters.fromYear) <= filters.toYear;
  }).sort((a, b) => (a.start_year ?? 9999) - (b.start_year ?? 9999) || a.id.localeCompare(b.id));
  const filteredHoldings = bundle.holdings.filter((holding) => {
    const place = placeById.get(holding.place_id)!;
    return layer === "current_holding_institution" && (!filters.place || holding.place_id === filters.place) &&
      (!filters.region || place.region === filters.region) && (!filters.precision || place.coordinate_precision === filters.precision);
  });
  const visibleFeatures = buildFeatures(filteredEpisodes, filteredHoldings, placeById);
  const currentSelectionId = selectedId(searchParams.get("episode"), bundle);
  const selectedEpisode = bundle.episodes.find((item) => item.id === currentSelectionId) ?? null;
  const selectedHolding = bundle.holdings.find((item) => item.id === currentSelectionId) ?? null;

  const selectFeature = (feature: MapFeature) => {
    const id = feature.properties.episodeId ?? feature.properties.holdingId ?? "";
    updateState({ episode: id });
    setLiveMessage(locale === "zh-CN" ? "已打开地点证据。" : "Place evidence opened.");
  };
  const resetFilters = () => updateState({ artist: null, place: null, episodeType: null, fromYear: null, toYear: null, region: null, precision: null, episode: null });
  const navigatorItems = layer === "artist_activity" ? filteredEpisodes.map((item) => item.id) : filteredHoldings.map((item) => item.id);
  const navigateSelection = (offset: number) => {
    if (!navigatorItems.length) return;
    const current = navigatorItems.indexOf(currentSelectionId);
    const next = navigatorItems[(current < 0 ? 0 : current + offset + navigatorItems.length) % navigatorItems.length];
    updateState({ episode: next });
  };

  return (
    <main id="main-content" className="art-map-page" tabIndex={-1}>
      <header className="map-hero">
        <div>
          <p className="eyebrow">{locale === "zh-CN" ? "来源支持的地点主张" : "Source-supported place claims"}</p>
          <h1>{locale === "zh-CN" ? "艺术时空地图" : "Art Across Time and Place"}</h1>
          <p className="map-dek">{locale === "zh-CN" ? "沿来源支持的地点主张阅读艺术家的生命与活动；地图、时间线和地点表使用同一状态，不把时间顺序画成旅行路线。" : "Read artists’ lives and activity through source-supported place claims. Map, timeline, and place table share one state and never turn chronology into a travel route."}</p>
        </div>
        <div className="map-release-stamp" aria-label={locale === "zh-CN" ? "正式发布状态" : "Formal release status"}>
          <span>{bundle.artists.length} / {bundle.places.length} / {bundle.episodes.length}</span><small>{locale === "zh-CN" ? "艺术家 · 地点 · episodes" : "artists · places · episodes"}</small>
          <b>{locale === "zh-CN" ? "已核验发布" : "VERIFIED RELEASE"}</b>
        </div>
      </header>

      <MapFiltersPanel bundle={bundle} filters={filters} locale={locale} updateState={updateState} reset={resetFilters} />

      <div className="map-view-toolbar">
        <div className="map-view-switch" role="group" aria-label={locale === "zh-CN" ? "视图" : "View"}>
          {(["map", "timeline", "list"] as MapView[]).map((item) => (
            <button key={item} type="button" aria-pressed={effectiveView === item} onClick={() => updateState({ view: item })}>
              {item === "map" ? (locale === "zh-CN" ? "地图" : "Map") : item === "timeline" ? (locale === "zh-CN" ? "时间线" : "Timeline") : (locale === "zh-CN" ? "地点表" : "Place table")}
            </button>
          ))}
        </div>
        <p><strong>{layerLabels[layer][locale === "zh-CN" ? 0 : 1]}</strong> · {layer === "artist_activity" ? filteredEpisodes.length : filteredHoldings.length}</p>
        <div className="map-actions"><button type="button" onClick={() => navigatorItems.length && updateState({ episode: navigatorItems[0] })}>{locale === "zh-CN" ? "首条" : "First"}</button><button type="button" onClick={() => navigateSelection(-1)}>{locale === "zh-CN" ? "上一条" : "Previous"}</button><button type="button" onClick={() => navigateSelection(1)}>{locale === "zh-CN" ? "下一条" : "Next"}</button></div>
      </div>

      <section className="map-workspace" aria-label={locale === "zh-CN" ? "地图与地点结果" : "Map and place results"}>
        <div className="map-primary-view">
          {effectiveView === "map" && (
            <div className="map-stage">
              <Suspense fallback={<p role="status" className="map-renderer-status">{locale === "zh-CN" ? "正在载入本地地图渲染器……" : "Loading the local map renderer…"}</p>}>
                <MapCanvas bundle={bundle} visibleFeatures={visibleFeatures} labelForFeature={(feature) => featureLabel(feature, placeById, artistById, locale)} onSelect={selectFeature} onFallback={() => { updateState({ view: "list" }); setLiveMessage(locale === "zh-CN" ? "地图渲染不可用，已切换到等价地点表。" : "Map rendering is unavailable; switched to the equivalent place table."); }} reducedMotion={reducedMotion} />
              </Suspense>
              <MarkerNavigator features={visibleFeatures} locale={locale} labelForFeature={(feature) => featureLabel(feature, placeById, artistById, locale)} onSelect={selectFeature} />
            </div>
          )}
          {effectiveView === "timeline" && <TimelineView episodes={filteredEpisodes} holdings={filteredHoldings} placeById={placeById} artistById={artistById} locale={locale} onSelect={(id) => updateState({ episode: id })} layer={layer} />}
          {effectiveView === "list" && <><p className="map-fallback-banner" hidden={view !== "map"}>{locale === "zh-CN" ? "当前偏好使用等价地点表；筛选、选择和 URL 状态保持不变。" : "Current preferences use the equivalent place table; filters, selection, and URL state are preserved."}</p><PlaceTable episodes={filteredEpisodes} holdings={filteredHoldings} placeById={placeById} artistById={artistById} locale={locale} onSelect={(id) => updateState({ episode: id })} layer={layer} /></>}
          {layer === "artwork_creation_place" && <div className="map-empty-state"><strong>0</strong><p>{locale === "zh-CN" ? `当前 ${bundle.artworks.length} 件作品没有可由正式来源明确闭合的创作地点，因此全部保持 not_asserted；这不是数据缺陷。` : `None of the ${bundle.artworks.length} artworks has an explicitly source-closed creation place, so all remain not_asserted. This is not a data defect.`}</p></div>}
        </div>
        <SelectionPanel ref={selectedPanelRef} episode={selectedEpisode} holding={selectedHolding} placeById={placeById} artistById={artistById} artworkById={artworkById} sourceById={sourceById} locale={locale} releaseId={bundle.manifest.id} />
      </section>

      <section className="map-method-grid" aria-label={locale === "zh-CN" ? "不确定性与方法" : "Uncertainty and method"}>
        <article><p className="eyebrow">{locale === "zh-CN" ? "空间精度" : "Spatial precision"}</p><h2>{locale === "zh-CN" ? "点不等于建筑" : "A point is not a building"}</h2><ul className="precision-legend"><li><span className="legend-dot" />{precisionLabels.locality[locale === "zh-CN" ? 0 : 1]}</li><li><span className="legend-halo legend-halo--small" />{precisionLabels.city_centroid[locale === "zh-CN" ? 0 : 1]}</li><li><span className="legend-halo" />{precisionLabels.regional_centroid[locale === "zh-CN" ? 0 : 1]}</li><li><span className="legend-list">≡</span>{precisionLabels.unknown[locale === "zh-CN" ? 0 : 1]}</li></ul></article>
        <article><p className="eyebrow">{locale === "zh-CN" ? "底图与边界" : "Basemap and borders"}</p><h2>{locale === "zh-CN" ? "只保留自然地理轮廓" : "Physical outlines only"}</h2><p>{locale === "zh-CN" ? "底图完全自托管，只含 land、coastline、lakes。现代地图轮廓不等于历史政治边界，未绘制现代国界。" : "The fully self-hosted basemap contains only land, coastline, and lakes. Modern outlines are not historical political borders; no modern borders are drawn."}</p><a href="https://www.naturalearthdata.com/" rel="noreferrer">Made with Natural Earth</a></article>
        <article><p className="eyebrow">{locale === "zh-CN" ? "限制" : "Limitations"}</p><h2>{locale === "zh-CN" ? "地图不是完整传记" : "The map is not a complete biography"}</h2><p>{locale === "zh-CN" ? "未显示地点不等于现实中不存在活动；地图中心不表示重要性；current holding institution 不等于作品创作地。" : "An omitted place does not prove no activity occurred; map position does not express importance; a current holding institution is not a creation place."}</p></article>
      </section>
      <div className="map-footer-actions"><button type="button" onClick={() => void navigator.clipboard?.writeText(window.location.href).then(() => setLiveMessage(locale === "zh-CN" ? "当前筛选链接已复制。" : "Filtered link copied."))}>{locale === "zh-CN" ? "复制分享链接" : "Copy share link"}</button><button type="button" onClick={() => window.print()}>{locale === "zh-CN" ? "打印时间线/地点表" : "Print timeline/place table"}</button><Link to="/art">← {locale === "zh-CN" ? "返回艺术序厅" : "Back to Art foyer"}</Link></div>
      <p className="sr-only" role="status" aria-live="polite">{liveMessage}</p>
    </main>
  );
}

function buildFeatures(episodes: ArtistEpisode[], holdings: HoldingLocation[], placeById: Map<string, PlaceIdentity>) {
  const features: MapFeature[] = [];
  for (const episode of episodes) {
    const place = placeById.get(episode.place_id)!;
    if (episode.release_status !== "verified_public" || !place.coordinates) continue;
    features.push({ type: "Feature", id: episode.id, geometry: { type: "Point", coordinates: place.coordinates }, properties: { episodeId: episode.id, artistId: episode.artist_id, placeId: place.id, episodeType: episode.episode_type, precision: episode.place_precision, layer: "artist_activity", uncertaintyKm: place.uncertainty_radius_km ?? 0 } });
  }
  for (const holding of holdings) {
    const place = placeById.get(holding.place_id)!;
    if (!place.coordinates) continue;
    features.push({ type: "Feature", id: holding.id, geometry: { type: "Point", coordinates: place.coordinates }, properties: { holdingId: holding.id, placeId: place.id, precision: place.coordinate_precision, layer: "current_holding_institution", uncertaintyKm: place.uncertainty_radius_km ?? 0 } });
  }
  return features;
}

function featureLabel(feature: MapFeature, placeById: Map<string, PlaceIdentity>, artistById: Map<string, { labels: LocalizedText }>, locale: "zh-CN" | "en") {
  const place = placeById.get(feature.properties.placeId)!;
  const artist = feature.properties.artistId ? artistById.get(feature.properties.artistId) : null;
  return `${artist ? `${localize(locale, artist.labels)} · ` : ""}${locale === "zh-CN" ? place.labels["zh-Hans"] : place.labels.en}`;
}

type UpdateState = (changes: Record<string, string | null>) => void;

function MapFiltersPanel({ bundle, filters, locale, updateState, reset }: { bundle: MapBundle; filters: MapFilters; locale: "zh-CN" | "en"; updateState: UpdateState; reset: () => void }) {
  const regions = [...new Set(bundle.places.map((item) => item.region))].sort();
  const types = [...new Set(bundle.episodes.map((item) => item.episode_type))].sort();
  const precisions = [...new Set(bundle.places.map((item) => item.coordinate_precision))];
  const min = bundle.mapIndex.year_range.min; const max = bundle.mapIndex.year_range.max;
  return <section className="map-filters" aria-labelledby="map-filters-title"><div className="map-filters-heading"><div><p className="eyebrow">{locale === "zh-CN" ? "共享状态" : "Shared state"}</p><h2 id="map-filters-title">{locale === "zh-CN" ? "筛选地点主张" : "Filter place claims"}</h2></div><button type="button" onClick={reset}>{locale === "zh-CN" ? "重置" : "Reset"}</button></div><div className="map-filter-grid">
    <label>{locale === "zh-CN" ? "艺术家" : "Artist"}<select value={filters.artist} onChange={(event) => updateState({ artist: event.target.value || null, episode: null })}><option value="">{locale === "zh-CN" ? "全部" : "All"}</option>{bundle.artists.map((item) => <option key={item.id} value={item.id}>{localize(locale, item.labels)}</option>)}</select></label>
    <label>{locale === "zh-CN" ? "地点" : "Place"}<select value={filters.place} onChange={(event) => updateState({ place: event.target.value || null, episode: null })}><option value="">{locale === "zh-CN" ? "全部" : "All"}</option>{bundle.places.map((item) => <option key={item.id} value={item.id}>{locale === "zh-CN" ? item.labels["zh-Hans"] : item.labels.en}</option>)}</select></label>
    <label>{locale === "zh-CN" ? "Episode 类型" : "Episode type"}<select value={filters.episodeType} onChange={(event) => updateState({ episodeType: event.target.value || null, episode: null })}><option value="">{locale === "zh-CN" ? "全部" : "All"}</option>{types.map((item) => <option key={item} value={item}>{episodeLabels[item]?.[locale === "zh-CN" ? 0 : 1] ?? item}</option>)}</select></label>
    <label>{locale === "zh-CN" ? "地区" : "Region"}<select value={filters.region} onChange={(event) => updateState({ region: event.target.value || null, episode: null })}><option value="">{locale === "zh-CN" ? "全部" : "All"}</option>{regions.map((item) => <option key={item}>{item}</option>)}</select></label>
    <label>{locale === "zh-CN" ? "空间精度" : "Spatial precision"}<select value={filters.precision} onChange={(event) => updateState({ precision: event.target.value || null, episode: null })}><option value="">{locale === "zh-CN" ? "全部" : "All"}</option>{precisions.map((item) => <option key={item} value={item}>{precisionLabels[item]?.[locale === "zh-CN" ? 0 : 1] ?? item}</option>)}</select></label>
    <label>{locale === "zh-CN" ? "图层" : "Layer"}<select value={filters.layer} onChange={(event) => updateState({ layer: event.target.value, episode: null })}>{(Object.keys(layerLabels) as MapLayer[]).map((item) => <option key={item} value={item}>{layerLabels[item][locale === "zh-CN" ? 0 : 1]}</option>)}</select></label>
  </div><fieldset className="year-filter"><legend>{locale === "zh-CN" ? "年份范围（仅离散 episode）" : "Year range (discrete episodes only)"}</legend><div><label>{locale === "zh-CN" ? "起年" : "From"}<input type="number" min={min} max={max} value={filters.fromYear} onChange={(event) => updateState({ fromYear: event.target.value })} /></label><input aria-label={locale === "zh-CN" ? "起始年份滑块" : "Start-year slider"} type="range" min={min} max={max} value={filters.fromYear} onChange={(event) => updateState({ fromYear: event.target.value })} /><input aria-label={locale === "zh-CN" ? "结束年份滑块" : "End-year slider"} type="range" min={min} max={max} value={filters.toYear} onChange={(event) => updateState({ toYear: event.target.value })} /><label>{locale === "zh-CN" ? "止年" : "To"}<input type="number" min={min} max={max} value={filters.toYear} onChange={(event) => updateState({ toYear: event.target.value })} /></label></div><p>{locale === "zh-CN" ? "时间范围不表示持续存在；circa 与不确定性保留在记录中。" : "A range does not imply continuous presence; circa and uncertainty remain explicit in each record."}</p></fieldset></section>;
}

function MarkerNavigator({ features, labelForFeature, onSelect, locale }: { features: MapFeature[]; labelForFeature: (item: MapFeature) => string; onSelect: (item: MapFeature) => void; locale: "zh-CN" | "en" }) {
  return <aside className="map-marker-navigator" aria-label={locale === "zh-CN" ? "与地图同步的地点标记列表" : "DOM place-marker list synchronized with the map"}><h2>{locale === "zh-CN" ? "地图标记" : "Map markers"}</h2>{features.length ? <ol>{features.map((feature) => <li key={feature.id}><button type="button" onClick={() => onSelect(feature)}><span className={`marker-symbol marker-symbol--${feature.properties.layer}`} aria-hidden="true" />{labelForFeature(feature)}<small>{precisionLabels[feature.properties.precision]?.[locale === "zh-CN" ? 0 : 1]}</small></button></li>)}</ol> : <p>{locale === "zh-CN" ? "当前筛选没有可绘制点；请查看地点表中的 list-only 记录。" : "No mappable points match; consult the place table for list-only records."}</p>}</aside>;
}

function TimelineView({ episodes, holdings, placeById, artistById, locale, onSelect, layer }: ResultsProps) {
  if (layer === "artwork_creation_place") return null;
  if (layer === "current_holding_institution") return <PlaceTable episodes={episodes} holdings={holdings} placeById={placeById} artistById={artistById} locale={locale} onSelect={onSelect} layer={layer} />;
  return <ol className="map-timeline" aria-label={locale === "zh-CN" ? "地点 episode 时间线" : "Place episode timeline"}>{episodes.map((episode) => { const place = placeById.get(episode.place_id)!; const artist = artistById.get(episode.artist_id)!; return <li key={episode.id}><button type="button" onClick={() => onSelect(episode.id)}><time>{yearText(episode)}</time><span><strong>{localize(locale, artist.labels)}</strong><b>{episodeLabels[episode.episode_type]?.[locale === "zh-CN" ? 0 : 1] ?? episode.episode_type}</b><span>{place.preferred_historical_label} <small>· {place.current_common_label}</small></span><em>{precisionLabels[episode.place_precision]?.[locale === "zh-CN" ? 0 : 1]}{episode.release_status === "verified_list_only" ? ` · ${locale === "zh-CN" ? "仅列表" : "list only"}` : ""}</em></span></button></li>; })}</ol>;
}

type ResultsProps = { episodes: ArtistEpisode[]; holdings: HoldingLocation[]; placeById: Map<string, PlaceIdentity>; artistById: Map<string, { labels: LocalizedText }>; locale: "zh-CN" | "en"; onSelect: (id: string) => void; layer: MapLayer };

function PlaceTable({ episodes, holdings, placeById, artistById, locale, onSelect, layer }: ResultsProps) {
  const rows = layer === "artist_activity" ? episodes.map((episode) => ({ id: episode.id, year: yearText(episode), subject: localize(locale, artistById.get(episode.artist_id)!.labels), kind: episodeLabels[episode.episode_type]?.[locale === "zh-CN" ? 0 : 1] ?? episode.episode_type, place: placeById.get(episode.place_id)! })) : holdings.map((holding) => ({ id: holding.id, year: "—", subject: locale === "zh-CN" ? "当前馆藏" : "Current holding", kind: `${holding.artwork_ids.length} ${locale === "zh-CN" ? "件作品" : "artworks"}`, place: placeById.get(holding.place_id)! }));
  return <div className="map-table-wrap"><table className="map-place-table"><caption>{locale === "zh-CN" ? "与地图、时间线使用相同筛选的地点表" : "Place table using the same filters as map and timeline"}</caption><thead><tr><th>{locale === "zh-CN" ? "年份" : "Year"}</th><th>{locale === "zh-CN" ? "艺术家/图层" : "Artist/layer"}</th><th>{locale === "zh-CN" ? "类型" : "Type"}</th><th>{locale === "zh-CN" ? "历史地点 / 当前名称" : "Historical place / current name"}</th><th>{locale === "zh-CN" ? "精度" : "Precision"}</th><th><span className="sr-only">{locale === "zh-CN" ? "查看" : "View"}</span></th></tr></thead><tbody>{rows.map((row) => <tr key={row.id}><td>{row.year}</td><td>{row.subject}</td><td>{row.kind}</td><td><strong>{row.place.preferred_historical_label}</strong><small>{row.place.current_common_label}</small></td><td>{precisionLabels[row.place.coordinate_precision]?.[locale === "zh-CN" ? 0 : 1]}</td><td><button type="button" onClick={() => onSelect(row.id)}>{locale === "zh-CN" ? "证据" : "Evidence"}</button></td></tr>)}</tbody></table>{rows.length === 0 && <p className="map-no-results">{locale === "zh-CN" ? "当前筛选没有正式记录。" : "No formal records match the filters."}</p>}</div>;
}

type SelectionProps = { episode: ArtistEpisode | null; holding: HoldingLocation | null; placeById: Map<string, PlaceIdentity>; artistById: Map<string, { labels: LocalizedText }>; artworkById: Map<string, { labels: LocalizedText }>; sourceById: Map<string, { name: string; url: string; license: string; attribution: string }>; locale: "zh-CN" | "en"; releaseId: string };

const SelectionPanel = forwardRef<HTMLElement, SelectionProps>(function SelectionPanel({ episode, holding, placeById, artistById, artworkById, sourceById, locale, releaseId }, ref) {
  if (!episode && !holding) return <aside className="map-selection map-selection--empty" ref={ref} tabIndex={-1}><p className="eyebrow">{locale === "zh-CN" ? "选择" : "Selection"}</p><h2>{locale === "zh-CN" ? "打开一条地点记录" : "Open a place record"}</h2><p>{locale === "zh-CN" ? "从地图标记、时间线或地点表选择；三种视图指向相同证据。" : "Choose from a map marker, timeline, or place table; all three views resolve to the same evidence."}</p></aside>;
  const place = placeById.get((episode ?? holding)!.place_id)!;
  const sourceIds = episode?.source_ids ?? holding!.source_ids;
  return <aside className="map-selection" ref={ref} tabIndex={-1} aria-labelledby="map-selection-title" data-release-id={releaseId}><p className="eyebrow">{locale === "zh-CN" ? "已核验地点记录" : "Verified place record"}</p><h2 id="map-selection-title">{episode ? localize(locale, artistById.get(episode.artist_id)!.labels) : (locale === "zh-CN" ? "当前馆藏机构" : "Current holding institution")}</h2><div className="place-name-pair"><strong>{place.preferred_historical_label}</strong><span>{locale === "zh-CN" ? "当前常用名" : "Current/common"}: {place.current_common_label}</span><small>{place.labels.source}</small></div>{episode ? <><dl><div><dt>{locale === "zh-CN" ? "类型" : "Type"}</dt><dd>{episodeLabels[episode.episode_type]?.[locale === "zh-CN" ? 0 : 1] ?? episode.episode_type}</dd></div><div><dt>{locale === "zh-CN" ? "时间" : "Time"}</dt><dd>{yearText(episode)} · {episode.date_precision}</dd></div><div><dt>{locale === "zh-CN" ? "空间精度" : "Spatial precision"}</dt><dd>{precisionLabels[episode.place_precision]?.[locale === "zh-CN" ? 0 : 1]}</dd></div><div><dt>{locale === "zh-CN" ? "置信度" : "Confidence"}</dt><dd>{episode.confidence}{episode.uncertain ? ` · ${locale === "zh-CN" ? "不确定" : "uncertain"}` : ""}</dd></div></dl><p className="selection-proof"><strong>{locale === "zh-CN" ? "证明什么" : "What it proves"}</strong>{episode.what_it_proves}</p><p className="selection-limit"><strong>{locale === "zh-CN" ? "不证明什么" : "What it does not prove"}</strong>{episode.does_not_prove}</p><details><summary>{locale === "zh-CN" ? "Evidence / Source" : "Evidence / Source"}</summary><ul>{episode.evidence.map((item) => <li key={item.id}><a href={item.locator} rel="noreferrer">{sourceById.get(item.source_id)?.name ?? item.source_id}</a><code>{item.record_sha256.slice(0, 22)}…</code></li>)}</ul></details></> : <><p className="selection-proof"><strong>{locale === "zh-CN" ? "证明什么" : "What it proves"}</strong>{holding!.what_it_proves}</p><p className="selection-limit"><strong>{locale === "zh-CN" ? "不证明什么" : "What it does not prove"}</strong>{holding!.does_not_prove}</p><details><summary>{holding!.artwork_ids.length} {locale === "zh-CN" ? "件相关作品" : "related artworks"}</summary><ul>{holding!.artwork_ids.map((id) => <li key={id}><Link to={`/art/artworks/${id}`}>{localize(locale, artworkById.get(id)!.labels)}</Link></li>)}</ul></details></>}<details><summary>{locale === "zh-CN" ? "来源与许可" : "Sources and licenses"}</summary><ul>{sourceIds.map((id) => { const source = sourceById.get(id); return <li key={id}>{source ? <a href={source.url} rel="noreferrer">{source.name} · {source.license}</a> : id}</li>; })}</ul></details><p className="coordinate-note">{place.coordinate_precision === "unknown" ? (locale === "zh-CN" ? "无可靠坐标：仅进入地点表与时间线。" : "No reliable coordinate: list and timeline only.") : `${place.coordinates?.join(", ")} · ${precisionLabels[place.coordinate_precision]?.[locale === "zh-CN" ? 0 : 1]}`}</p></aside>;
});

function MapUnavailable({ locale }: { locale: "zh-CN" | "en" }) {
  return <main id="main-content" className="inner-page" tabIndex={-1}><p className="eyebrow">{locale === "zh-CN" ? "完整性保护" : "Integrity protection"}</p><h1>{locale === "zh-CN" ? "地图资料暂不可用" : "Map material is unavailable"}</h1><p className="page-lede">{locale === "zh-CN" ? "当前静态资料未通过浏览器完整性核验，因此没有展示不完整地点资料。" : "The current static material did not pass browser integrity checks, so incomplete place material was not displayed."}</p><Link className="text-link" to="/art">← {locale === "zh-CN" ? "返回艺术序厅" : "Back to Art foyer"}</Link></main>;
}

export default ArtMapPage;
