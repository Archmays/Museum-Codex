import {
  startTransition,
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useReducer,
  useRef,
  useState,
  type ComponentProps,
  type KeyboardEvent,
} from "react";
import { Link, useSearchParams } from "react-router-dom";
import { loadArtConstellationRelease, type ArtConstellationLoadResult } from "../../data/release-loader";
import { useI18n } from "../../i18n/I18nProvider";
import { usePreferences } from "../../preferences/PreferencesProvider";
import {
  DetailPanel,
  type OpenPanel,
  type PanelLoadState,
} from "./DetailPanel";
import {
  constellationReducer,
  createConstellationState,
  deriveConstellationView,
  stateToSearchParams,
  type ConstellationDerivationState,
} from "./model";
import type {
  ArtConstellationDataSource,
  ArtConstellationRelease,
  ArtistSources,
  RelationshipDetails,
  RelationshipIndex,
  RightsDetails,
  ViewMode,
} from "./types";
import { localize } from "./types";
import { ArtistListView, EmptyView, GraphView, RelationshipTableView } from "./Views";
import { planConstellationGraph } from "./scale-strategy";
import "./art-constellation.css";
import { currentArtReleaseBaseUrl } from "../../data/art-release-profile";

if (typeof performance !== "undefined" && typeof performance.mark === "function") {
  performance.mark("museum04-route-module");
}

type LoadedProps = {
  release: ArtConstellationRelease;
  dataSource: ArtConstellationDataSource;
};

type PanelHostHandle = {
  open: (panel: OpenPanel, trigger?: HTMLElement) => void;
};

type DetailPanelProps = ComponentProps<typeof DetailPanel>;
type PanelHostProps = Pick<
  DetailPanelProps,
  | "release"
  | "relationshipIndex"
  | "artistSources"
  | "relationshipDetails"
  | "rightsDetails"
  | "locale"
  | "copy"
  | "lowBandwidth"
  | "onRetryIndex"
  | "onSelectRelationship"
> & {
  loadArtistSources: (artistId: string) => Promise<void>;
  loadRelationshipDetails: (relationshipId: string) => Promise<void>;
  loadRights: () => Promise<void>;
  onPanelClosed: (panel: OpenPanel) => void;
};

const PanelHost = forwardRef<PanelHostHandle, PanelHostProps>(function PanelHost(
  {
    loadArtistSources,
    loadRelationshipDetails,
    loadRights,
    onPanelClosed,
    ...detailProps
  },
  ref,
) {
  const [panel, setPanel] = useState<OpenPanel | null>(null);
  const restoreFocusTo = useRef<HTMLElement | null>(null);
  const shellRef = useRef<HTMLElement | null>(null);
  const activePanel = useRef<OpenPanel | null>(null);
  const panelFrame = useRef<number | null>(null);

  useEffect(() => () => {
    if (panelFrame.current !== null) cancelAnimationFrame(panelFrame.current);
  }, []);

  useImperativeHandle(ref, () => ({
    open(nextPanel, trigger) {
      if (trigger && !trigger.closest(".constellation-detail-panel")) restoreFocusTo.current = trigger;
      const replacingOpenPanel = activePanel.current !== null;
      activePanel.current = nextPanel;
      const shell = shellRef.current;
      if (shell) {
        const title = shell.querySelector<HTMLElement>("#constellation-panel-accessible-title");
        if (title) {
          title.textContent = nextPanel.kind === "artist"
            ? detailProps.copy.artistPanel
            : nextPanel.kind === "relationship"
              ? detailProps.copy.relationshipPanel
              : detailProps.copy.rightsPanel;
        }
        const staleContentTitle = shell.querySelector<HTMLElement>("#constellation-panel-content-title");
        if (staleContentTitle) staleContentTitle.hidden = true;
        if (replacingOpenPanel) {
          const scroll = shell.querySelector<HTMLElement>(".panel-scroll");
          if (scroll) scroll.hidden = true;
        }
        shell.hidden = false;
        shell.removeAttribute("aria-hidden");
        shell.setAttribute("aria-labelledby", "constellation-panel-accessible-title");
        shell.dataset.panelKind = nextPanel.kind;
        if (nextPanel.kind === "rights") delete shell.dataset.panelId;
        else shell.dataset.panelId = nextPanel.id;
      }
      if (replacingOpenPanel) {
        setPanel(nextPanel);
      } else {
        if (panelFrame.current !== null) cancelAnimationFrame(panelFrame.current);
        panelFrame.current = requestAnimationFrame(() => {
          panelFrame.current = null;
          setPanel(nextPanel);
        });
      }
    },
  }), [detailProps.copy.artistPanel, detailProps.copy.relationshipPanel, detailProps.copy.rightsPanel]);

  const close = useCallback(() => {
    const closedPanel = activePanel.current;
    if (!closedPanel) return;
    activePanel.current = null;
    if (panelFrame.current !== null) {
      cancelAnimationFrame(panelFrame.current);
      panelFrame.current = null;
    }
    if (shellRef.current) {
      shellRef.current.hidden = true;
      shellRef.current.setAttribute("aria-hidden", "true");
      shellRef.current.removeAttribute("aria-labelledby");
    }
    setPanel(null);
    onPanelClosed(closedPanel);
    requestAnimationFrame(() => restoreFocusTo.current?.focus({ preventScroll: true }));
  }, [onPanelClosed]);

  return (
    <DetailPanel
      {...detailProps}
      ref={shellRef}
      panel={panel}
      onClose={close}
      onRetryArtistSources={() => panel?.kind === "artist" && void loadArtistSources(panel.id)}
      onRetryRelationship={() => panel?.kind === "relationship" && void loadRelationshipDetails(panel.id)}
      onRetryRights={() => void loadRights()}
    />
  );
});

function fill(template: string, values: Record<string, string | number>) {
  return Object.entries(values).reduce((text, [key, value]) => text.replace(`{${key}}`, String(value)), template);
}

function mark(name: string) {
  if (typeof performance !== "undefined" && typeof performance.mark === "function") performance.mark(name);
}

function LoadedConstellation({ release, dataSource }: LoadedProps) {
  const { locale, t } = useI18n();
  const { compactViewport, forcedColors, lowBandwidth } = usePreferences();
  const [searchParams, setSearchParams] = useSearchParams();
  const [state, dispatch] = useReducer(
    constellationReducer,
    undefined,
    () => createConstellationState(searchParams, release),
  );
  const [relationshipIndex, setRelationshipIndex] = useState<PanelLoadState<RelationshipIndex>>({ status: "idle" });
  const [artistSources, setArtistSources] = useState<PanelLoadState<ArtistSources>>({ status: "idle" });
  const [relationshipDetails, setRelationshipDetails] = useState<PanelLoadState<RelationshipDetails>>({ status: "idle" });
  const [rightsDetails, setRightsDetails] = useState<PanelLoadState<RightsDetails>>({ status: "idle" });
  const [announcement, setAnnouncement] = useState("");
  const [graphUnavailable, setGraphUnavailable] = useState(false);
  const [experienceMounted, setExperienceMounted] = useState(false);
  const viewTabs = useRef<Array<HTMLButtonElement | null>>([]);
  const panelHost = useRef<PanelHostHandle>(null);
  const indexAbort = useRef<AbortController | null>(null);
  const artistAbort = useRef<AbortController | null>(null);
  const relationshipAbort = useRef<AbortController | null>(null);
  const rightsAbort = useRef<AbortController | null>(null);
  const artistSelectionFrame = useRef<number | null>(null);
  const relationshipSelectionFrame = useRef<number | null>(null);
  const initialDeepLinkHandled = useRef(false);

  const graphSuppressed = compactViewport || lowBandwidth || forcedColors;
  const graphDisabled = graphSuppressed || graphUnavailable;
  const graphFallbackAnnouncement = graphUnavailable
    ? t.constellation.graphUnavailable
    : lowBandwidth
    ? t.constellation.lowBandwidthGraph
    : forcedColors
      ? t.constellation.forcedColorsGraph
      : t.constellation.compactViewportGraph;
  const effectiveView: ViewMode = graphDisabled && state.view === "graph" ? "list" : state.view;
  const [graphRetained, setGraphRetained] = useState(effectiveView === "graph");
  const indexData = relationshipIndex.status === "loaded" ? relationshipIndex.data : null;
  const derivationState = useMemo<ConstellationDerivationState>(() => ({
    query: state.query,
    relationshipType: state.relationshipType,
    level: state.level,
    period: state.period,
    region: state.region,
    tradition: state.tradition,
    contextType: state.contextType,
    focusArtistId: state.focusArtistId,
    selectedRelationshipId: state.selectedRelationshipId,
  }), [
    state.contextType,
    state.focusArtistId,
    state.level,
    state.period,
    state.query,
    state.region,
    state.relationshipType,
    state.selectedRelationshipId,
    state.tradition,
  ]);
  const viewModel = useMemo(
    () => deriveConstellationView(release, indexData, derivationState),
    [derivationState, indexData, release],
  );
  const contextTypes = useMemo(
    () => [...new Set(indexData?.contexts.map((context) => context.type) ?? [])].sort(),
    [indexData],
  );

  useEffect(() => {
    mark("museum04-initial-data-ready");
    const frame = requestAnimationFrame(() => setExperienceMounted(true));
    return () => cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    if (experienceMounted && effectiveView !== "graph" && viewModel.artists.length > 0) mark("museum04-experience-ready");
  }, [effectiveView, experienceMounted, viewModel.artists.length]);

  useEffect(() => {
    setSearchParams(stateToSearchParams(state, release.version), { replace: true });
  }, [release.version, setSearchParams, state]);

  useEffect(() => {
    if (state.view !== "graph" || !graphDisabled) return;
    const timer = window.setTimeout(() => {
      setGraphRetained(false);
      dispatch({ type: "set-view", view: "list" });
      setAnnouncement(graphFallbackAnnouncement);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [graphDisabled, graphFallbackAnnouncement, state.view]);

  useEffect(() => () => {
    indexAbort.current?.abort();
    artistAbort.current?.abort();
    relationshipAbort.current?.abort();
    rightsAbort.current?.abort();
    if (artistSelectionFrame.current !== null) cancelAnimationFrame(artistSelectionFrame.current);
    if (relationshipSelectionFrame.current !== null) cancelAnimationFrame(relationshipSelectionFrame.current);
  }, []);

  const loadIndex = useCallback(async () => {
    if (relationshipIndex.status === "loaded" || relationshipIndex.status === "loading") return;
    indexAbort.current?.abort();
    const controller = new AbortController();
    indexAbort.current = controller;
    setRelationshipIndex({ status: "loading" });
    const result = await dataSource.loadRelationshipIndex(controller.signal);
    if (controller.signal.aborted) return;
    setRelationshipIndex(result.status === "loaded" ? { status: "loaded", data: result.data } : { status: "failed" });
  }, [dataSource, relationshipIndex.status]);

  const retryIndex = useCallback(async () => {
    setRelationshipIndex({ status: "idle" });
    indexAbort.current?.abort();
    const controller = new AbortController();
    indexAbort.current = controller;
    setRelationshipIndex({ status: "loading" });
    const result = await dataSource.loadRelationshipIndex(controller.signal);
    if (!controller.signal.aborted) {
      setRelationshipIndex(result.status === "loaded" ? { status: "loaded", data: result.data } : { status: "failed" });
    }
  }, [dataSource]);

  const loadArtistSources = useCallback(async (artistId: string) => {
    artistAbort.current?.abort();
    const controller = new AbortController();
    artistAbort.current = controller;
    setArtistSources({ status: "loading" });
    const result = await dataSource.loadArtistSources(artistId, controller.signal);
    if (!controller.signal.aborted) {
      setArtistSources(result.status === "loaded" ? { status: "loaded", data: result.data } : { status: "failed" });
    }
  }, [dataSource]);

  const loadRelationshipDetails = useCallback(async (relationshipId: string) => {
    relationshipAbort.current?.abort();
    const controller = new AbortController();
    relationshipAbort.current = controller;
    setRelationshipDetails({ status: "loading" });
    const result = await dataSource.loadRelationshipDetails(relationshipId, controller.signal);
    if (!controller.signal.aborted) {
      setRelationshipDetails(result.status === "loaded" ? { status: "loaded", data: result.data } : { status: "failed" });
    }
  }, [dataSource]);

  const loadRights = useCallback(async () => {
    rightsAbort.current?.abort();
    const controller = new AbortController();
    rightsAbort.current = controller;
    setRightsDetails({ status: "loading" });
    const result = await dataSource.loadRights(controller.signal);
    if (!controller.signal.aborted) {
      setRightsDetails(result.status === "loaded" ? { status: "loaded", data: result.data } : { status: "failed" });
    }
  }, [dataSource]);

  useEffect(() => {
    if (
      state.focusArtistId || state.selectedRelationshipId || state.view === "table" ||
      state.query.trim() || state.relationshipType !== "all" || state.level !== "all" ||
      state.period || state.region || state.tradition || state.contextType
    ) {
      const timer = window.setTimeout(() => void loadIndex(), 0);
      return () => window.clearTimeout(timer);
    }
  }, [
    loadIndex,
    state.contextType,
    state.focusArtistId,
    state.level,
    state.period,
    state.query,
    state.region,
    state.relationshipType,
    state.selectedRelationshipId,
    state.tradition,
    state.view,
  ]);

  useEffect(() => {
    if (initialDeepLinkHandled.current) return;
    const timer = window.setTimeout(() => {
      if (state.selectedRelationshipId) {
        if (relationshipIndex.status !== "loaded") return;
        initialDeepLinkHandled.current = true;
        const relationship = relationshipIndex.data.relationships.find((candidate) => candidate.id === state.selectedRelationshipId);
        if (!relationship) {
          dispatch({ type: "select-relationship", relationshipId: null });
          return;
        }
        panelHost.current?.open({ kind: "relationship", id: relationship.id });
        setAnnouncement(fill(t.constellation.selectedRelationship, { title: localize(relationship.title, locale) }));
        void loadRelationshipDetails(relationship.id);
        return;
      }
      if (state.focusArtistId) {
        initialDeepLinkHandled.current = true;
        panelHost.current?.open({ kind: "artist", id: state.focusArtistId });
        void loadArtistSources(state.focusArtistId);
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadArtistSources, loadRelationshipDetails, locale, relationshipIndex, state.focusArtistId, state.selectedRelationshipId, t.constellation.selectedRelationship]);

  const selectArtist = useCallback((artistId: string, trigger?: HTMLElement) => {
    const artist = release.artists.find((candidate) => candidate.id === artistId);
    if (!artist) return;
    initialDeepLinkHandled.current = true;
    panelHost.current?.open({ kind: "artist", id: artistId }, trigger);
    if (artistSelectionFrame.current !== null) cancelAnimationFrame(artistSelectionFrame.current);
    artistSelectionFrame.current = requestAnimationFrame(() => {
      artistSelectionFrame.current = null;
      setAnnouncement(fill(t.constellation.selectedArtist, { name: localize(artist.labels, locale), count: artist.relationCount }));
      void loadArtistSources(artistId);
      startTransition(() => dispatch({ type: "focus-artist", artistId }));
    });
  }, [loadArtistSources, locale, release.artists, t.constellation.selectedArtist]);

  const selectRelationship = useCallback((relationshipId: string, trigger?: HTMLElement) => {
    const relationship = indexData?.relationships.find((candidate) => candidate.id === relationshipId);
    if (!relationship) return;
    initialDeepLinkHandled.current = true;
    panelHost.current?.open({ kind: "relationship", id: relationshipId }, trigger);
    if (relationshipSelectionFrame.current !== null) cancelAnimationFrame(relationshipSelectionFrame.current);
    relationshipSelectionFrame.current = requestAnimationFrame(() => {
      relationshipSelectionFrame.current = null;
      setAnnouncement(fill(t.constellation.selectedRelationship, { title: localize(relationship.title, locale) }));
      void loadRelationshipDetails(relationshipId);
      startTransition(() => dispatch({ type: "select-relationship", relationshipId }));
    });
  }, [indexData, loadRelationshipDetails, locale, t.constellation.selectedRelationship]);

  const rendererReady = useCallback(() => {
    mark("museum04-renderer-ready");
    mark("museum04-experience-ready");
  }, []);
  const rendererUnavailable = useCallback(() => {
    setGraphUnavailable(true);
    setGraphRetained(false);
    dispatch({ type: "set-view", view: "list" });
    setAnnouncement(t.constellation.graphUnavailable);
  }, [t.constellation.graphUnavailable]);

  const openRights = (trigger: HTMLElement) => {
    panelHost.current?.open({ kind: "rights" }, trigger);
    void loadRights();
  };

  const panelClosed = useCallback((closedPanel: OpenPanel) => {
    if (closedPanel.kind === "relationship") dispatch({ type: "select-relationship", relationshipId: null });
    artistAbort.current?.abort();
    relationshipAbort.current?.abort();
    rightsAbort.current?.abort();
  }, []);

  const selectView = (view: ViewMode) => {
    if (view === "graph" && graphDisabled) {
      setAnnouncement(graphFallbackAnnouncement);
      return;
    }
    if (view === "graph") setGraphRetained(true);
    dispatch({ type: "set-view", view });
    setAnnouncement({ graph: t.constellation.graphAnnounce, list: t.constellation.listAnnounce, table: t.constellation.tableAnnounce }[view]);
  };

  const navigateTabs = (event: KeyboardEvent<HTMLButtonElement>, currentIndex: number) => {
    const keys = ["ArrowLeft", "ArrowRight", "Home", "End"];
    if (!keys.includes(event.key)) return;
    event.preventDefault();
    const enabledIndices = (["graph", "list", "table"] as const)
      .map((view, index) => ({ view, index }))
      .filter(({ view }) => view !== "graph" || !graphDisabled)
      .map(({ index }) => index);
    const currentPosition = Math.max(0, enabledIndices.indexOf(currentIndex));
    let nextIndex = currentIndex;
    if (event.key === "Home") nextIndex = enabledIndices[0];
    if (event.key === "End") nextIndex = enabledIndices.at(-1) ?? currentIndex;
    if (event.key === "ArrowLeft") nextIndex = enabledIndices[(currentPosition + enabledIndices.length - 1) % enabledIndices.length];
    if (event.key === "ArrowRight") nextIndex = enabledIndices[(currentPosition + 1) % enabledIndices.length];
    viewTabs.current[nextIndex]?.focus();
    startTransition(() => selectView((["graph", "list", "table"] as const)[nextIndex]));
  };

  const summary = relationshipIndex.status === "loaded" ? fill(t.constellation.visibleSummary, {
    artists: viewModel.artists.length,
    relationships: viewModel.relationships.length,
    hiddenArtists: viewModel.hiddenArtistCount,
    hiddenRelationships: viewModel.hiddenRelationshipCount,
  }) : fill(t.constellation.visibleSummaryDeferred, { artists: viewModel.artists.length });
  const sharedProps = {
    artists: viewModel.artists,
    relationships: viewModel.relationships,
    locale,
    copy: t.constellation,
    focusArtistId: state.focusArtistId,
    selectedRelationshipId: state.selectedRelationshipId,
    matchReasons: viewModel.matchReasons,
    relationshipIndexLoaded: relationshipIndex.status === "loaded",
    onSelectArtist: selectArtist,
    onSelectRelationship: selectRelationship,
  };
  const graphScalePlan = planConstellationGraph(
    viewModel.artists,
    viewModel.graphRelationships,
    state.focusArtistId,
  );
  const graphSharedProps = {
    ...sharedProps,
    artists: graphScalePlan.artists,
    relationships: graphScalePlan.relationships,
  };

  return (
    <main
      id="main-content"
      className="constellation-page"
      tabIndex={-1}
      data-museum04-status="ready"
      data-view={effectiveView}
    >
      <header className="constellation-hero">
        <div>
          <p className="eyebrow">{t.constellation.eyebrow}</p>
          <h1>{localize(release.summary.title, locale)}</h1>
          <p>{t.constellation.intro}</p>
        </div>
        <dl className="release-stamp">
          <div>
            <dt>{t.constellation.releaseLabel}</dt>
            <dd>{release.version}</dd>
          </div>
          <div><dt>{t.constellation.level}</dt><dd>{release.summary.levelCounts.A} / {release.summary.levelCounts.B} / {release.summary.levelCounts.C} · A / B / C</dd></div>
          <div><dt>{t.constellation.type}</dt><dd>{release.summary.artistCount} / {release.summary.contextCount} / {release.summary.relationshipCount}</dd></div>
          <div><dt>{t.constellation.mediaRights}</dt><dd>{release.summary.approvedMediaArtworkCount} / {release.summary.artworkCount} · {release.summary.mediaCount}</dd></div>
        </dl>
      </header>

      {experienceMounted ? (
        <>
      <section className="semantic-notice" aria-label={t.constellation.levelsTitle}>
        <span className="semantic-mark" aria-hidden="true">C</span>
        <div>
          <h2>{t.constellation.levelC}</h2>
          <p>{localize(release.summary.semantics, locale)}</p>
        </div>
        <button type="button" onClick={(event) => openRights(event.currentTarget)}>{t.constellation.openRights}</button>
      </section>

      <section className="constellation-controls" aria-label={t.constellation.viewLabel}>
        <div className="view-tabs" role="tablist" aria-label={t.constellation.viewLabel}>
          {(["graph", "list", "table"] as const).map((view, index) => (
            <button
              key={view}
              ref={(node) => { viewTabs.current[index] = node; }}
              id={`constellation-tab-${view}`}
              role="tab"
              type="button"
              aria-controls="constellation-view-panel"
              aria-selected={effectiveView === view}
              tabIndex={effectiveView === view ? 0 : -1}
              disabled={view === "graph" && graphDisabled}
              onKeyDown={(event) => navigateTabs(event, index)}
              onClick={() => selectView(view)}
            >
              <span>{String(index + 1).padStart(2, "0")}</span>
              {{ graph: t.constellation.graphView, list: t.constellation.listView, table: t.constellation.tableView }[view]}
            </button>
          ))}
        </div>
        <div className="filter-grid">
          <label className="search-control">
            <span>{t.constellation.searchLabel}</span>
            <input
              type="search"
              value={state.query}
              placeholder={t.constellation.searchPlaceholder}
              onChange={(event) => dispatch({ type: "set-query", query: event.currentTarget.value })}
            />
          </label>
          <label>
            <span>{t.constellation.relationshipType}</span>
            <select value={state.relationshipType} onChange={(event) => dispatch({ type: "set-relationship-type", relationshipType: event.currentTarget.value as typeof state.relationshipType })}>
              <option value="all">{t.constellation.allTypes}</option>
              <option value="shared_subject">{t.constellation.sharedSubject}</option>
              <option value="shared_material">{t.constellation.sharedMaterial}</option>
              <option value="shared_technique">{t.constellation.sharedTechnique}</option>
            </select>
          </label>
          <label>
            <span>{t.constellation.levelFilter}</span>
            <select value={state.level} onChange={(event) => dispatch({ type: "set-level", level: event.currentTarget.value as typeof state.level })}>
              <option value="all">{t.constellation.allLevels}</option>
              <option value="A">{t.constellation.levelA}</option>
              <option value="B">{t.constellation.levelB}</option>
              <option value="C">{t.constellation.levelC}</option>
            </select>
          </label>
          <label>
            <span>{t.constellation.period}</span>
            <select value={state.period} onChange={(event) => dispatch({ type: "set-period", period: event.currentTarget.value })}>
              <option value="">{t.constellation.allPeriods}</option>
              {release.facets.periods.map((period) => <option key={period} value={period}>{period}</option>)}
            </select>
          </label>
          <label>
            <span>{t.constellation.region}</span>
            <select value={state.region} onChange={(event) => dispatch({ type: "set-region", region: event.currentTarget.value })}>
              <option value="">{t.constellation.allRegions}</option>
              {release.facets.regions.map((region) => <option key={region} value={region}>{region}</option>)}
            </select>
          </label>
          <label>
            <span>{t.constellation.tradition}</span>
            <select value={state.tradition} onChange={(event) => dispatch({ type: "set-tradition", tradition: event.currentTarget.value })}>
              <option value="">{t.constellation.allTraditions}</option>
              {release.facets.traditions.map((tradition) => <option key={tradition} value={tradition}>{tradition}</option>)}
            </select>
          </label>
          <label>
            <span>{t.constellation.contextType}</span>
            <select value={state.contextType} onFocus={() => void loadIndex()} onChange={(event) => dispatch({ type: "set-context-type", contextType: event.currentTarget.value })}>
              <option value="">{t.constellation.allContexts}</option>
              {contextTypes.map((contextType) => <option key={contextType} value={contextType}>{({
                material: t.constellation.contextMaterial,
                technique: t.constellation.contextTechnique,
                subject: t.constellation.contextSubject,
              } as Record<string, string>)[contextType] ?? contextType}</option>)}
            </select>
          </label>
          <button className="reset-control" type="button" onClick={() => dispatch({ type: "reset" })}>{t.constellation.resetFilters}</button>
        </div>
      </section>

      <div className="constellation-status-line" role="status">
        <p>{summary}</p>
        {graphUnavailable ? <p>{t.constellation.graphUnavailable}</p> : null}
        {(state.level === "A" || state.level === "B") ? <p>{t.constellation.noAbRelations}</p> : null}
        {relationshipIndex.status === "loading" ? <p>{t.constellation.relationsLoading}</p> : null}
        {relationshipIndex.status === "failed" ? <FailedIndex copy={t.constellation.detailError} retry={t.constellation.retry} onRetry={() => void retryIndex()} /> : null}
      </div>

      <section className="constellation-workspace" aria-label={t.constellation.viewLabel}>
        <aside className="constellation-legend" aria-labelledby="constellation-legend-title">
          <h2 id="constellation-legend-title">{t.constellation.levelsTitle}</h2>
          <ul>
            <li><span className="legend-edge subject" aria-hidden="true" />{t.constellation.sharedSubject}</li>
            <li><span className="legend-edge material" aria-hidden="true" />{t.constellation.sharedMaterial}</li>
            <li><span className="legend-edge technique" aria-hidden="true" />{t.constellation.sharedTechnique}</li>
          </ul>
          <p>{t.constellation.levelAEmpty}</p>
          <p>{t.constellation.levelBEmpty}</p>
          <p>{t.constellation.levelCCount}</p>
          <p>{t.constellation.algorithmDisabled}</p>
          <p>{t.constellation.distanceNotice}</p>
        </aside>
        <div
          id="constellation-view-panel"
          className="constellation-view"
          role="tabpanel"
          aria-labelledby={`constellation-tab-${effectiveView}`}
        >
          {viewModel.artists.length === 0 ? <EmptyView copy={t.constellation} /> : null}
          {viewModel.artists.length > 0 && (graphRetained || effectiveView === "graph") ? (
            <div className="constellation-retained-graph" hidden={effectiveView !== "graph"}>
              {graphScalePlan.limited ? (
                <p className="constellation-scale-note" role="status">
                  {locale === "zh-CN"
                    ? `图形视图显示聚焦邻域与稳定 ID 有界子图（${graphScalePlan.artists.length}/${graphScalePlan.totalArtists} 节点）；完整任务请使用分页文字列表与关系表。`
                    : `The graph shows a bounded focus-neighborhood and stable-ID subgraph (${graphScalePlan.artists.length}/${graphScalePlan.totalArtists} nodes). Use the paginated text list and relationship table for the complete task.`}
                </p>
              ) : null}
              <GraphView
                {...graphSharedProps}
                layout={release.layout}
                relatedArtistIds={viewModel.relatedArtistIds}
                onRendererReady={rendererReady}
                onRendererUnavailable={rendererUnavailable}
              />
            </div>
          ) : null}
          {viewModel.artists.length > 0 ? (
            <div className="constellation-retained-list" hidden={effectiveView !== "list"}>
              <ArtistListView {...sharedProps} />
            </div>
          ) : null}
          {viewModel.artists.length > 0 && relationshipIndex.status === "loaded" ? (
            <div hidden={effectiveView !== "table"}>
              <RelationshipTableView {...sharedProps} contexts={relationshipIndex.data.contexts} />
            </div>
          ) : null}
          {viewModel.artists.length > 0 && effectiveView === "table" && relationshipIndex.status !== "loaded" ? <LoadingTable copy={t.constellation.relationsLoading} /> : null}
        </div>
      </section>

      <div className="sr-only" aria-live="polite" aria-atomic="true">{announcement}</div>
      <Link className="text-link constellation-back-link" to="/art">{t.constellation.backFoyer}</Link>
      <Link className="text-link constellation-back-link" to="/art/map">{locale === "zh-CN" ? "艺术时空地图" : "Art Across Time and Place"}</Link>
        </>
      ) : <div className="constellation-experience-placeholder" aria-hidden="true" />}
      <PanelHost
        ref={panelHost}
        release={release}
        relationshipIndex={relationshipIndex}
        artistSources={artistSources}
        relationshipDetails={relationshipDetails}
        rightsDetails={rightsDetails}
        locale={locale}
        copy={t.constellation}
        lowBandwidth={lowBandwidth}
        onRetryIndex={() => void retryIndex()}
        onSelectRelationship={selectRelationship}
        loadArtistSources={loadArtistSources}
        loadRelationshipDetails={loadRelationshipDetails}
        loadRights={loadRights}
        onPanelClosed={panelClosed}
      />
    </main>
  );
}

function FailedIndex({ copy, retry, onRetry }: { copy: string; retry: string; onRetry: () => void }) {
  return <span role="alert">{copy} <button type="button" onClick={onRetry}>{retry}</button></span>;
}

function LoadingTable({ copy }: { copy: string }) {
  return <div className="constellation-inline-loading" role="status">{copy}</div>;
}

export default function ArtConstellationPage() {
  const { t } = useI18n();
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<ArtConstellationLoadResult | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    void loadArtConstellationRelease(
      currentArtReleaseBaseUrl(),
      fetch,
      controller.signal,
    ).then((next) => {
      if (!controller.signal.aborted) setResult(next);
    });
    return () => controller.abort();
  }, [attempt]);

  if (!result) {
    return <main id="main-content" className="constellation-page constellation-load-state" tabIndex={-1} data-museum04-status="loading" data-view="pending"><p role="status">{t.constellation.loading}</p></main>;
  }
  if (result.status !== "loaded") {
    return (
      <main id="main-content" className="constellation-page constellation-load-state" tabIndex={-1} data-museum04-status="error" data-view="unavailable">
        <p className="eyebrow">{t.constellation.eyebrow}</p>
        <h1>{t.constellation.loadErrorTitle}</h1>
        <p>{t.constellation.loadErrorText}</p>
        <button className="primary-button" type="button" onClick={() => {
          setResult(null);
          setAttempt((value) => value + 1);
        }}>{t.constellation.retry}</button>
        <Link className="text-link" to="/art">{t.constellation.backFoyer}</Link>
      </main>
    );
  }
  return <LoadedConstellation release={result.release} dataSource={result.dataSource} />;
}
