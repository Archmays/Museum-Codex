import { useCallback, useEffect, useRef } from "react";
import type { GeoJSONSource, Map as MapLibreMap, Marker as MapLibreMarker } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { loadMapGeometry } from "./map-loader";
import type { MapBundle, MapFeature } from "./types";

type Props = {
  bundle: MapBundle;
  visibleFeatures: MapFeature[];
  labelForFeature: (feature: MapFeature) => string;
  onSelect: (feature: MapFeature) => void;
  onFallback: () => void;
  reducedMotion: boolean;
};

function webGlAvailable() {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

export function MapCanvas({ bundle, visibleFeatures, labelForFeature, onSelect, onFallback, reducedMotion }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markersRef = useRef<MapLibreMarker[]>([]);
  const featuresRef = useRef(visibleFeatures);
  const labelRef = useRef(labelForFeature);
  const selectRef = useRef(onSelect);
  const fallbackRef = useRef(onFallback);

  useEffect(() => {
    featuresRef.current = visibleFeatures;
    labelRef.current = labelForFeature;
    selectRef.current = onSelect;
    fallbackRef.current = onFallback;
  }, [labelForFeature, onFallback, onSelect, visibleFeatures]);

  const renderMarkers = useCallback(async () => {
    const map = mapRef.current;
    if (!map) return;
    const { Marker } = await import("maplibre-gl");
    markersRef.current.forEach((marker) => marker.remove());
    const grouped = new Map<string, MapFeature[]>();
    for (const feature of featuresRef.current) {
      const key = `${feature.properties.layer}:${feature.properties.placeId}`;
      grouped.set(key, [...(grouped.get(key) ?? []), feature]);
    }
    markersRef.current = [...grouped.values()].map((features) => {
      const first = features[0];
      const button = document.createElement("button");
      button.type = "button";
      button.className = `map-place-marker map-place-marker--${first.properties.layer}`;
      button.setAttribute("aria-label", `${labelRef.current(first)} · ${features.length}`);
      button.innerHTML = `<span aria-hidden="true"></span><b aria-hidden="true">${features.length}</b>`;
      button.addEventListener("click", () => selectRef.current(first));
      return new Marker({ element: button, anchor: "center" })
        .setLngLat(first.geometry.coordinates)
        .addTo(map);
    });
  }, []);

  useEffect(() => {
    if (!containerRef.current || !webGlAvailable()) {
      fallbackRef.current();
      return;
    }
    let disposed = false;
    let contextCanvas: HTMLCanvasElement | null = null;
    const initialise = async () => {
      try {
        const [{ Map }, geometry] = await Promise.all([import("maplibre-gl"), loadMapGeometry(bundle)]);
        if (disposed || !containerRef.current) return;
        const style = structuredClone(bundle.style.style);
        style.sources.land.data = geometry.land as never;
        style.sources.coastline.data = geometry.coastline as never;
        style.sources.lakes.data = geometry.lakes as never;
        style.sources.places.data = { type: "FeatureCollection", features: featuresRef.current } as never;
        style.layers = style.layers.filter((layer) => layer.id !== "place-markers");
        const map = new Map({
          container: containerRef.current,
          style: style as never,
          center: [0, 20],
          zoom: 0.72,
          minZoom: 0.7,
          maxZoom: 8,
          pitch: 0,
          bearing: 0,
          cooperativeGestures: true,
          dragRotate: false,
          pitchWithRotate: false,
          attributionControl: false,
          fadeDuration: reducedMotion ? 0 : 100,
        });
        mapRef.current = map;
        map.touchZoomRotate.disableRotation();
        map.on("load", () => { void renderMarkers(); });
        map.on("error", () => fallbackRef.current());
        contextCanvas = map.getCanvas();
        contextCanvas.addEventListener("webglcontextlost", fallbackRef.current);
      } catch {
        fallbackRef.current();
      }
    };
    void initialise();
    return () => {
      disposed = true;
      if (contextCanvas) contextCanvas.removeEventListener("webglcontextlost", fallbackRef.current);
      markersRef.current.forEach((marker) => marker.remove());
      markersRef.current = [];
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, [bundle, reducedMotion, renderMarkers]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.isStyleLoaded()) return;
    const source = map.getSource("places");
    if (source?.type === "geojson") {
      (source as GeoJSONSource).setData({ type: "FeatureCollection", features: visibleFeatures });
    }
    void renderMarkers();
  }, [renderMarkers, visibleFeatures]);

  return <div className="art-map-canvas" ref={containerRef} role="region" aria-label="艺术地点二维地图 / Two-dimensional art place map" />;
}
