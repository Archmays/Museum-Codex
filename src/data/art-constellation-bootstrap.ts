const INITIAL_FILES = [
  "manifest.json",
  "artists.json",
] as const;

export type BootstrappedArtifact = {
  status: number;
  ok: boolean;
  bytes: ArrayBuffer;
};

type BootstrapScope = typeof globalThis & {
  __MUSEUM04_BOOTSTRAP__?: Map<string, Promise<BootstrappedArtifact>>;
};

const scope = globalThis as BootstrapScope;
const artifacts = scope.__MUSEUM04_BOOTSTRAP__ ?? new Map<string, Promise<BootstrappedArtifact>>();
scope.__MUSEUM04_BOOTSTRAP__ = artifacts;

export function preloadArtConstellationData(baseUrl: string) {
  const base = new URL(baseUrl, window.location.href);
  for (const name of INITIAL_FILES) {
    const url = new URL(name, base).href;
    if (artifacts.has(url)) continue;
    const pending = fetch(url, { headers: { Accept: "application/json" } })
      .then(async (response) => ({
        status: response.status,
        ok: response.ok,
        bytes: await response.arrayBuffer(),
      }))
      .catch((error) => {
        artifacts.delete(url);
        throw error;
      });
    artifacts.set(url, pending);
  }
}

export async function readBootstrappedArtifact(url: string, signal?: AbortSignal) {
  const pending = artifacts.get(url);
  if (!pending) return null;
  if (signal?.aborted) throw new DOMException("The operation was aborted", "AbortError");
  const artifact = await pending;
  if (signal?.aborted) throw new DOMException("The operation was aborted", "AbortError");
  return artifact;
}
