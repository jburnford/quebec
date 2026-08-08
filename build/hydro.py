"""Build build/hydro.json: detailed water polygons for the upper Ottawa River.

    python build/hydro.py

The Natural Earth linework in inland.json is fine at valley scale but far too
coarse for the Act III township close-up, where it cuts straight through the
Westmeath lot fabric. This fetches real water polygons (river, lakes, and the
islands as holes — Allumette, Calumet, the Rocher Fendu channels) from
OpenStreetMap via Overpass, clips them to the upper-valley window, simplifies,
and writes build/hydro.json (committed). Rebuilding the page never refetches;
delete build/_osm_cache/ to force a refresh.

Data © OpenStreetMap contributors, ODbL — credited in the page notes.
Requires shapely.
"""
import json
import os
import urllib.parse
import urllib.request

import shapely
from shapely.geometry import Polygon
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "_osm_cache")
OUT = os.path.join(HERE, "hydro.json")

# upper Ottawa window: Chats Falls up past Allumette Island, both shores
BBOX = (45.40, -77.90, 46.25, -76.00)          # s, w, n, e (Overpass order)
CLIP = shapely.box(BBOX[1], BBOX[0], BBOX[3], BBOX[2])
MIN_AREA_KM2 = 0.6              # the river, its islands, and the named lakes;
                                # anything smaller is noise at these spans
MIN_HOLE_KM2 = 0.15             # islands can be smaller than lakes and still matter
SIMPLIFY_DEG = 0.0006           # ~50 m — one pixel at the deepest zoom
ROUND = 4                       # ~11 m

QUERY = f"""
[out:json][timeout:180][bbox:{BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]}];
(
  way["natural"="water"](if: length() > 300);
  relation["natural"="water"];
  way["waterway"="riverbank"];
  relation["waterway"="riverbank"];
);
out geom;
"""


def fetch():
    os.makedirs(CACHE, exist_ok=True)
    cached = os.path.join(CACHE, "osm_water.json")
    if os.path.exists(cached):
        print("using cached Overpass response")
        return json.load(open(cached, encoding="utf-8"))
    req = urllib.request.Request(
        "https://overpass-api.de/api/interpreter",
        data=("data=" + urllib.parse.quote(QUERY)).encode(),
        headers={"User-Agent": "quebec-arrivals-viz/1.0"})
    with urllib.request.urlopen(req, timeout=300) as r:
        data = json.load(r)
    json.dump(data, open(cached, "w", encoding="utf-8"))
    print(f"fetched {len(data['elements'])} elements from Overpass")
    return data


def ring_of(way_geom):
    pts = [(p["lon"], p["lat"]) for p in way_geom]
    return pts if len(pts) >= 4 and pts[0] == pts[-1] else None


def polygons(data):
    """Ways -> simple polygons; multipolygon relations -> polygons with holes."""
    polys = []
    for el in data["elements"]:
        if el["type"] == "way" and "geometry" in el:
            r = ring_of(el["geometry"])
            if r:
                polys.append(Polygon(r))
        elif el["type"] == "relation" and "members" in el:
            outers, inners = [], []
            for m in el["members"]:
                if m["type"] != "way" or "geometry" not in m:
                    continue
                pts = [(p["lon"], p["lat"]) for p in m["geometry"]]
                (outers if m.get("role") != "inner" else inners).append(pts)
            # stitch member ways into closed rings (they arrive fragmented)
            for group, sink in ((outers, "o"), (inners, "i")):
                rings, pool = [], [p for p in group if len(p) >= 2]
                while pool:
                    ring = pool.pop(0)
                    grew = True
                    while ring[0] != ring[-1] and grew:
                        grew = False
                        for k, cand in enumerate(pool):
                            if cand[0] == ring[-1]:
                                ring += cand[1:]
                            elif cand[-1] == ring[-1]:
                                ring += cand[-2::-1]
                            elif cand[-1] == ring[0]:
                                ring = cand + ring[1:]
                            elif cand[0] == ring[0]:
                                ring = cand[::-1] + ring[1:]
                            else:
                                continue
                            pool.pop(k)
                            grew = True
                            break
                    if ring[0] == ring[-1] and len(ring) >= 4:
                        rings.append(ring)
                if sink == "o":
                    out_rings = rings
                else:
                    in_rings = rings
            out_rings = out_rings if outers else []
            in_rings = in_rings if inners else []
            for orng in out_rings:
                shell = Polygon(orng)
                holes = [h for h in in_rings if shell.contains(Polygon(h).representative_point())]
                polys.append(Polygon(orng, holes))
    return polys


def main():
    data = fetch()
    polys = [p for p in polygons(data) if p.is_valid or not p.is_empty]
    polys = [p if p.is_valid else shapely.make_valid(p) for p in polys]
    print(f"assembled {len(polys)} polygons")

    merged = unary_union(polys).intersection(CLIP)
    parts = list(merged.geoms) if merged.geom_type in ("MultiPolygon", "GeometryCollection") \
        else [merged]
    km2 = 111.32 * 111.32 * 0.694          # deg^2 -> km^2 at 46 N, crude but fine
    keep = [p for p in parts if p.geom_type == "Polygon" and p.area * km2 >= MIN_AREA_KM2]
    print(f"kept {len(keep)} water bodies >= {MIN_AREA_KM2} km2")

    out = []
    for p in keep:
        p = p.simplify(SIMPLIFY_DEG)
        if p.is_empty or p.geom_type != "Polygon":
            continue
        rec = {"o": [[round(x, ROUND), round(y, ROUND)] for x, y in p.exterior.coords[:-1]]}
        holes = []
        for hole in p.interiors:
            if abs(Polygon(hole).area) * km2 < MIN_HOLE_KM2:
                continue
            holes.append([[round(x, ROUND), round(y, ROUND)] for x, y in hole.coords[:-1]])
        if holes:
            rec["h"] = holes
        out.append(rec)

    payload = {"meta": {"bbox": [BBOX[1], BBOX[0], BBOX[3], BBOX[2]],
                        "source": "OpenStreetMap contributors, ODbL"},
               "water": out}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))
    n_holes = sum(len(r.get("h", [])) for r in out)
    print(f"wrote {OUT} ({os.path.getsize(OUT)/1024:.0f} KB, "
          f"{len(out)} polygons, {n_holes} islands)")


if __name__ == "__main__":
    main()
