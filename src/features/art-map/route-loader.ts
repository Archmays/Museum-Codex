let artMapRoute: ReturnType<typeof importArtMapRoute> | undefined;

function importArtMapRoute() {
  return import("./ArtMapPage");
}

export function preloadArtMapRoute() {
  artMapRoute ??= importArtMapRoute();
  return artMapRoute;
}
