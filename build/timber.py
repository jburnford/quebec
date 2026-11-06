"""Export the timber-industry point layer to build/timber.json for Act III.

    python build/timber.py

Reads E:\\Timber_Industry_History.geojson — a point layer compiled by Jim
Clifford (2020, ArcGIS Online) from period sources: sawmills, timber slides,
booms and dams, and recorded pine/timber stands, each dated and cited to the
source that records it (Sherriff's 1829 survey, gazetteers, county histories).

Writes build/timber.json (committed), so rebuilding the page never needs the
external drive. Each point keeps what the page draws and what its tooltip
shows: [lon, lat, year, class, kind, name, note, source, km], trimmed. km is
the point's position along the Ottawa measured from Montreal (projected onto
a schematic river line, so tributary sites count by how far up the valley
they sit); null for sites outside the Ottawa watershed. The page uses it to
track how far upriver the documented trade has reached.
"""
import json
import math
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = r"E:\Timber_Industry_History.geojson"
OUT = os.path.join(HERE, "timber.json")

ROUND = 4

# class 0: mills · 1: river works (slides, booms, dams) · 2: timber/pine stands
MILLS = {"sawmill", "mill"}
WORKS = {"timber slide", "slide", "dam", "pier dam", "timber boom",
         "timber canal and booms", "timber cove"}


def cls(species):
    s = ("" if species is None else str(species)).strip().lower()
    if s in MILLS:
        return 0
    if s in WORKS:
        return 1
    return 2


def clip(s, n):
    """Whitespace-normalise and cut at a word boundary with an ellipsis."""
    s = re.sub(r"\s+", " ", ("" if s is None else str(s))).strip()
    if len(s) <= n:
        return s
    return s[:n].rsplit(" ", 1)[0].rstrip(",;:") + "…"


# The Ottawa, Montreal to Lake Timiskaming, as (lat, lon) waypoints. Schematic
# — it measures position up the valley, it is not drawn anywhere.
RIVER = [(45.50, -73.57), (45.47, -74.00), (45.57, -74.38), (45.60, -74.62),
         (45.60, -75.00), (45.48, -75.65), (45.42, -75.72), (45.52, -76.14),
         (45.47, -76.24), (45.57, -76.45), (45.72, -76.75), (45.82, -76.90),
         (45.86, -77.11), (46.10, -77.49), (46.19, -77.70), (46.32, -78.70),
         (46.71, -79.10)]
NEAR_KM = 80             # a site counts as Ottawa-watershed within this


def _xy(lat, lon, lat0):
    """Local planar km (equirectangular; fine at valley scale)."""
    return (lon * 111.32 * math.cos(math.radians(lat0)), lat * 110.57)


def river_km(lat, lon):
    """(distance along RIVER from Montreal, offset from the line), in km."""
    px_, py_ = _xy(lat, lon, lat)
    best = (1e9, 0.0)    # (offset, distance along)
    run = 0.0
    for (a, b) in zip(RIVER, RIVER[1:]):
        ax, ay = _xy(a[0], a[1], lat)
        bx, by = _xy(b[0], b[1], lat)
        vx, vy = bx - ax, by - ay
        seg = math.hypot(vx, vy)
        t = 0.0 if seg == 0 else max(0.0, min(1.0, ((px_ - ax) * vx + (py_ - ay) * vy) / (seg * seg)))
        qx, qy = ax + t * vx, ay + t * vy
        off = math.hypot(px_ - qx, py_ - qy)
        if off < best[0]:
            best = (off, run + t * seg)
        run += seg
    return best[1], best[0]


with open(SRC, encoding="utf-8") as f:
    g = json.load(f)

pts, skipped, undated = [], 0, 0
for feat in g["features"]:
    geom = feat.get("geometry")
    if not geom or geom.get("type") != "Point":
        skipped += 1
        continue
    lon, lat = geom["coordinates"][:2]
    p = feat.get("properties", {})
    y = p.get("Year")
    y = int(y) if y else 0          # 0 = undated: shown once the layer is on
    if not y:
        undated += 1
    along, off = river_km(lat, lon)
    km = int(round(along)) if off <= NEAR_KM else None
    pts.append([round(lon, ROUND), round(lat, ROUND), y, cls(p.get("Species")),
                clip(p.get("Species"), 40), clip(p.get("Name"), 80),
                clip(p.get("Note"), 360), clip(p.get("Source"), 160), km])

pts.sort(key=lambda r: (r[2] or 9999, r[0]))
years = [p[2] for p in pts if p[2]]
payload = {
    "meta": {
        "n": len(pts),
        "mills": sum(1 for p in pts if p[3] == 0),
        "works": sum(1 for p in pts if p[3] == 1),
        "stands": sum(1 for p in pts if p[3] == 2),
        "undated": undated,
        "years": [min(years), max(years)],
        "source": ("Timber Industry History point layer, compiled by Jim "
                   "Clifford (2020) from period sources incl. Alexander "
                   "Sherriff's 1829 Topographical Notices; each point is "
                   "dated and cited in the source file. Underpins Clifford & "
                   "Castonguay, J. of Historical Geography 78 (2022), "
                   "doi:10.1016/j.jhg.2022.05.002."),
    },
    "pts": pts,
}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(payload, f, separators=(",", ":"), ensure_ascii=False)

m = payload["meta"]
print(f"points: {m['n']} (skipped {skipped} without geometry)")
print(f"mills {m['mills']}  river works {m['works']}  stands {m['stands']}  "
      f"undated {m['undated']}  years {m['years'][0]}-{m['years'][1]}")
print(f"wrote {OUT} ({os.path.getsize(OUT)/1024:.1f} KB)")
