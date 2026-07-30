"""
Standard web-mercator (XYZ/slippy-map) tile math -- the WebODM/Django-side
mirror of `embeddings-tapis-actors/embed_generate/webodm_client.py`'s own
tile-math section (same functions, same formulas, deliberately kept
byte-for-byte equivalent so both sides of this system agree on what a given
(z, x, y) actually covers on the ground). That module's HTTP-fetching parts
(`get_tile_coverage()`/`fetch_tile()`) have no equivalent here -- WebODM's own
views already have direct, in-process access to the raster (via
`app/api/tiler.py`'s `COGReader`/`Task.orthophoto_extent`), so there's no HTTP
round-trip to itself to make.

Not a bespoke grid -- this is the OSM "Slippy map tilenames" convention,
same as WebODM's own tiler and every other XYZ tile consumer (Decision 9).
"""

import math


def lonlat_to_tile(lon, lat, zoom):
    """Returns the (x, y) tile containing (lon, lat) at `zoom`."""
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n)
    return x, y


def tile_to_lonlat(x, y, zoom):
    """Returns the (lon, lat) of the NW corner of tile (x, y) at `zoom`."""
    n = 2.0 ** zoom
    lon = x / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat = math.degrees(lat_rad)
    return lon, lat


def tile_bounds_lonlat(x, y, zoom):
    """Returns (west, south, east, north) for tile (x, y, zoom)."""
    west, north = tile_to_lonlat(x, y, zoom)
    east, south = tile_to_lonlat(x + 1, y + 1, zoom)
    return west, south, east, north


def tile_center_lonlat(x, y, zoom):
    """Returns (lat, lon) of the center of tile (x, y, zoom)."""
    west, south, east, north = tile_bounds_lonlat(x, y, zoom)
    return (south + north) / 2.0, (west + east) / 2.0


def tile_bounds_wkt(x, y, zoom):
    """Returns a WKT POLYGON (SRID 4326 implied, applied by the caller's SQL
    `ST_GeomFromText(%s, 4326)`) for `tile_grid.bounds` -- a closed ring,
    matching PostGIS's own WKT polygon convention. Byte-for-byte the same
    formula as embed_generate/webodm_client.py's own tile_bounds_wkt(), so a
    tile written by labeling and the same tile written by embed-generate
    produce identical bounds geometry for the same (site, z, x, y)."""
    west, south, east, north = tile_bounds_lonlat(x, y, zoom)
    return (
        f"POLYGON(({west} {south}, {east} {south}, {east} {north}, "
        f"{west} {north}, {west} {south}))"
    )


def meters_per_pixel(zoom, lat, tile_size=256):
    """Standard web-mercator ground resolution formula (meters/pixel at a
    given zoom and latitude, for the conventional 256px tile)."""
    return 156543.03392804097 * math.cos(math.radians(lat)) / (2 ** zoom) * (256 / tile_size)


def candidate_tiles(bounds, zoom):
    """
    Yields every (x, y) tile at `zoom` whose bbox overlaps `bounds` (west,
    south, east, north) -- the CANDIDATE set from bbox math alone, not the
    final coverage set. Callers should filter each candidate against real
    per-tile coverage (WebODM's own `COGReader.tile_exists(z, x, y)`,
    Decision 9) -- a non-rectangular flight footprint means some candidates
    here won't actually be covered, which is expected, not an error.
    """
    west, south, east, north = bounds
    x_min, y_min = lonlat_to_tile(west, north, zoom)
    x_max, y_max = lonlat_to_tile(east, south, zoom)
    for x in range(min(x_min, x_max), max(x_min, x_max) + 1):
        for y in range(min(y_min, y_max), max(y_min, y_max) + 1):
            yield x, y
