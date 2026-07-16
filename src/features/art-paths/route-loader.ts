let artPathsRoute: ReturnType<typeof importArtPathsRoute> | undefined;

function importArtPathsRoute() {
  return import("./ArtPathsPage");
}

export function preloadArtPathsRoute() {
  artPathsRoute ??= importArtPathsRoute();
  return artPathsRoute;
}
