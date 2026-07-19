let artSearchRoute: ReturnType<typeof importArtSearchRoute> | undefined;

function importArtSearchRoute() {
  return import("./ArtSearchPage");
}

export function preloadArtSearchRoute() {
  artSearchRoute ??= importArtSearchRoute();
  return artSearchRoute;
}
