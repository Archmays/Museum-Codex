let artConstellationRoute: ReturnType<typeof importArtConstellationRoute> | undefined;

function importArtConstellationRoute() {
  return import("./ArtConstellationPage");
}

export function preloadArtConstellationRoute() {
  artConstellationRoute ??= importArtConstellationRoute();
  return artConstellationRoute;
}
