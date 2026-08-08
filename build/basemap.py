"""Fetch Natural Earth basemaps and derive the two clipped, simplified files the
visualization embeds: coast.json (Atlantic, 110m) and inland.json (the
St Lawrence-Ottawa corridor, 50m land/lakes/rivers).

Both outputs are committed, so you only need to run this to regenerate them.

    python build/basemap.py
"""
import json, math, os, io, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "_ne_cache")
os.makedirs(CACHE, exist_ok=True)

SOURCES = {
    "land-110m.json": "https://cdn.jsdelivr.net/npm/world-atlas@2/land-110m.json",
    "ne_50m_land.geojson":
        "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_land.geojson",
    "ne_50m_lakes.geojson":
        "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_lakes.geojson",
    "ne_50m_rivers_lake_centerlines.geojson":
        "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_rivers_lake_centerlines.geojson",
}


def fetch(name):
    path = os.path.join(CACHE, name)
    if not os.path.exists(path):
        print("downloading", name)
        urllib.request.urlretrieve(SOURCES[name], path)
    return path


def simplify(pts, tol):
    """Ramer-Douglas-Peucker, iterative."""
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i0, i1 = stack.pop()
        if i1 <= i0 + 1:
            continue
        x0, y0 = pts[i0]
        x1, y1 = pts[i1]
        dx, dy = x1 - x0, y1 - y0
        den = math.hypot(dx, dy)
        best, bi = -1.0, -1
        for i in range(i0 + 1, i1):
            x, y = pts[i]
            d = (abs(dy * x - dx * y + x1 * y0 - y1 * x0) / den) if den > 0 \
                else math.hypot(x - x0, y - y0)
            if d > best:
                best, bi = d, i
        if best > tol:
            keep[bi] = True
            stack.append((i0, bi))
            stack.append((bi, i1))
    return [p for p, k in zip(pts, keep) if k]


def bbox_hit(ring, win):
    lon0, lon1, lat0, lat1 = win
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return not (max(xs) < lon0 or min(xs) > lon1 or max(ys) < lat0 or min(ys) > lat1)


# ---------------------------------------------------------------- Atlantic
def build_coast():
    topo = json.load(io.open(fetch("land-110m.json"), encoding="utf-8"))
    tr = topo["transform"]
    sx, sy = tr["scale"]
    tx, ty = tr["translate"]

    def decode(arc):
        x = y = 0
        out = []
        for dx, dy in arc:
            x += dx
            y += dy
            out.append((x * sx + tx, y * sy + ty))
        return out

    arcs = [decode(a) for a in topo["arcs"]]

    def ring(idxs):
        pts = []
        for i in idxs:
            a = arcs[~i][::-1] if i < 0 else arcs[i]
            pts.extend(a if not pts else a[1:])
        return pts

    rings = []
    for geom in topo["objects"]["land"]["geometries"]:
        polys = [geom["arcs"]] if geom["type"] == "Polygon" else geom["arcs"]
        for poly in polys:
            for r in poly:
                rings.append(ring(r))

    win = (-85.0, 32.0, 2.0, 66.0)
    out = []
    for r in rings:
        if not bbox_hit(r, win):
            continue
        s = simplify(r, 0.12)
        if len(s) < 4:
            continue
        out.append([[round(x, 2), round(y, 2)] for x, y in s])
    out.sort(key=len, reverse=True)
    return out


# ------------------------------------------------------ St Lawrence / Ottawa
INLAND_WIN = (-86.0, -63.0, 40.0, 53.0)

def rings_of(geom):
    t, c = geom["type"], geom["coordinates"]
    if t == "Polygon":
        return list(c)
    if t == "MultiPolygon":
        return [r for poly in c for r in poly]
    if t == "LineString":
        return [c]
    if t == "MultiLineString":
        return list(c)
    return []


def load_geo(name, tol, minpts, keep_names=None):
    gj = json.load(io.open(fetch(name), encoding="utf-8"))
    out = []
    for f in gj["features"]:
        g = f.get("geometry")
        if not g:
            continue
        if keep_names is not None:
            props = f.get("properties") or {}
            nm = " ".join(str(props.get(k, "")) for k in ("name", "name_en")).lower()
            if not any(w in nm for w in keep_names):
                continue
        for r in rings_of(g):
            if not r or not bbox_hit(r, INLAND_WIN):
                continue
            s = simplify(r, tol)
            if len(s) < minpts:
                continue
            out.append([[round(x, 3), round(y, 3)] for x, y in s])
    return out


def build_inland():
    return {
        "land":  load_geo("ne_50m_land.geojson", 0.02, 4),
        "lakes": load_geo("ne_50m_lakes.geojson", 0.015, 4),
        # only the rivers this story needs, so the map stays legible
        "rivers": load_geo("ne_50m_rivers_lake_centerlines.geojson", 0.012, 2,
                           keep_names=["ottawa", "st. lawrence", "saint lawrence",
                                       "st lawrence", "saguenay", "richelieu",
                                       "st. maurice", "saint-maurice", "gatineau"]),
    }


if __name__ == "__main__":
    coast = build_coast()
    io.open(os.path.join(HERE, "coast.json"), "w", encoding="utf-8").write(
        json.dumps(coast, separators=(",", ":")))
    print(f"coast.json  {len(coast)} rings, {sum(len(r) for r in coast)} points")

    inland = build_inland()
    io.open(os.path.join(HERE, "inland.json"), "w", encoding="utf-8").write(
        json.dumps(inland, separators=(",", ":")))
    print("inland.json land %d / lakes %d / rivers %d"
          % (len(inland["land"]), len(inland["lakes"]), len(inland["rivers"])))
