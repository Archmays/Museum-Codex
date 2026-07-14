import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

const STORAGE_KEY = "museum-low-bandwidth";

type PreferencesContextValue = {
  compactViewport: boolean;
  lowBandwidth: boolean;
  reducedMotion: boolean;
  forcedColors: boolean;
  toggleLowBandwidth: () => void;
};

const PreferencesContext = createContext<PreferencesContextValue | null>(null);

function readLowBandwidth() {
  try {
    return localStorage.getItem(STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

function getReducedMotionPreference() {
  return typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function getForcedColorsPreference() {
  return typeof matchMedia === "function" && matchMedia("(forced-colors: active)").matches;
}

function getCompactViewportPreference() {
  return typeof matchMedia === "function" && matchMedia("(max-width: 374px)").matches;
}

export function PreferencesProvider({ children }: { children: ReactNode }) {
  const [lowBandwidth, setLowBandwidth] = useState(readLowBandwidth);
  const [reducedMotion, setReducedMotion] = useState(getReducedMotionPreference);
  const [forcedColors, setForcedColors] = useState(getForcedColorsPreference);
  const [compactViewport, setCompactViewport] = useState(getCompactViewportPreference);

  useEffect(() => {
    const query = matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    const query = matchMedia("(forced-colors: active)");
    const update = () => setForcedColors(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    const query = matchMedia("(max-width: 374px)");
    const update = () => setCompactViewport(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.bandwidth = lowBandwidth ? "low" : "full";
    document.documentElement.dataset.compactViewport = compactViewport ? "active" : "none";
    document.documentElement.dataset.motion = reducedMotion ? "reduced" : "full";
    document.documentElement.dataset.forcedColors = forcedColors ? "active" : "none";
  }, [compactViewport, forcedColors, lowBandwidth, reducedMotion]);

  const toggleLowBandwidth = () => {
    setLowBandwidth((current) => {
      const next = !current;
      try {
        localStorage.setItem(STORAGE_KEY, String(next));
      } catch {
        // The preference still applies to the current visit.
      }
      return next;
    });
  };

  const value = useMemo(
    () => ({ compactViewport, lowBandwidth, reducedMotion, forcedColors, toggleLowBandwidth }),
    [compactViewport, forcedColors, lowBandwidth, reducedMotion],
  );

  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>;
}

export function usePreferences() {
  const context = useContext(PreferencesContext);
  if (!context) {
    throw new Error("usePreferences must be used inside PreferencesProvider");
  }
  return context;
}
