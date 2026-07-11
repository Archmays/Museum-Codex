import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

const STORAGE_KEY = "museum-low-bandwidth";

type PreferencesContextValue = {
  lowBandwidth: boolean;
  reducedMotion: boolean;
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

export function PreferencesProvider({ children }: { children: ReactNode }) {
  const [lowBandwidth, setLowBandwidth] = useState(readLowBandwidth);
  const [reducedMotion, setReducedMotion] = useState(getReducedMotionPreference);

  useEffect(() => {
    const query = matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.bandwidth = lowBandwidth ? "low" : "full";
    document.documentElement.dataset.motion = reducedMotion ? "reduced" : "full";
  }, [lowBandwidth, reducedMotion]);

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
    () => ({ lowBandwidth, reducedMotion, toggleLowBandwidth }),
    [lowBandwidth, reducedMotion],
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
