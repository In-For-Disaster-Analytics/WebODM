// Mirrors coreplugins/embeddings/tile_math.py exactly (same formulas) --
// standard web-mercator (XYZ/slippy-map) tile math -- so the map picker
// draws the exact same tile bounds the backend itself used to compute
// candidate tiles from. Only the one function the map picker actually
// needs (tile bounds, as a Leaflet LatLngBounds-shaped array) is ported;
// see tile_math.py for the full set (bounds_wkt, meters_per_pixel, etc.)
// that only the server side needs.

export function tileToLonLat(x, y, zoom) {
    const n = Math.pow(2, zoom);
    const lon = (x / n) * 360.0 - 180.0;
    const latRad = Math.atan(Math.sinh(Math.PI * (1 - (2 * y) / n)));
    const lat = (latRad * 180.0) / Math.PI;
    return [lon, lat];
}

// Returns [[south, west], [north, east]] -- Leaflet's own LatLngBounds
// constructor order (`L.latLngBounds(corner1, corner2)`/`L.rectangle(bounds)`).
export function tileBoundsLatLng(x, y, zoom) {
    const [west, north] = tileToLonLat(x, y, zoom);
    const [east, south] = tileToLonLat(x + 1, y + 1, zoom);
    return [[south, west], [north, east]];
}
