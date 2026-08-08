"""Export the Westmeath Township lot fabric and land-patent index to
build/westmeath.json for Act III.

    python build/westmeath.py

Reads from the HGIS Lab share (G:), which holds the research materials behind
Clifford & Huckerby (2025), figures 5-8:

  Renfrew.gdb / Lot_fabric_improved_history   the surveyed lot polygons
  Index/westmeath_index_original_copy.csv     lot-by-lot patent index: the date
                                              and name of each lot's first Crown
                                              grant or sale, transcribed from
                                              Ontario land records

Writes build/westmeath.json (committed), so rebuilding the page never needs
the share. Requires pyogrio, shapely, pyproj, pandas.
"""
import json
import os

import pandas as pd
import pyogrio.raw
import shapely
from pyproj import Transformer
from shapely.ops import transform

HERE = os.path.dirname(os.path.abspath(__file__))
GDB = r"G:\HGIS LAB\Huckerby\Renfrew\Renfrew.gdb"
IDX = r"G:\HGIS LAB\Huckerby\Renfrew\Index\westmeath_index_original_copy.csv"
OUT = os.path.join(HERE, "westmeath.json")

SIMPLIFY_M = 20          # metres; the source lots are survey-precise
ROUND = 4                # ~11 m at this latitude — matches the tolerance

# The individuals the article documents as holding both Westmeath farms and
# timber licences or timber-firm ties (Clifford & Huckerby 2025, figs 7-8).
# Full-name matches only: Mary Adams, Joseph Tucker and Mosses B Bellows are
# different people.
TIMBER = {
    "john egan": "John Egan",
    "hugh carmichael": "Hugh Carmichael",
    "huch carmichael": "Hugh Carmichael",       # spelling variant in the index
    "caleb s bellows": "Caleb S. Bellows",
    "samuel adams": "Samuel Adams",
    "george r tucker": "George R. Tucker",
}

# ---------------------------------------------------------------- lots
meta, _, geoms, fields = pyogrio.raw.read(GDB, layer="Lot_fabric_improved_history",
                                          return_fids=False)
tbl = pd.DataFrame({name: col for name, col in zip(meta["fields"], fields)})
tbl["geom"] = shapely.from_wkb(geoms)

w = tbl[(tbl["GEOGRAPHIC"] == "WESTMEATH")
        & (tbl["CLASS_SUBT"] == "Lot, Improved")].reset_index(drop=True)
print(f"lots: {len(w)} (of {len(tbl)} features in the fabric)")

# ---------------------------------------------------------------- index
idx = pd.read_csv(IDX)
idx = idx[idx["OGF_ID"].notna()].copy()
idx["OGF_ID"] = idx["OGF_ID"].astype(int)

date_cols = [f"Index{i}_date" for i in range(1, 9)]
name_cols = [f"Index{i}_name" for i in range(1, 9)]
trans_cols = [f"Index{i}_trans" for i in range(1, 9)]

by_lot = {}
for r in idx.itertuples():
    entries = []
    for dc, nc, tc in zip(date_cols, name_cols, trans_cols):
        d = pd.to_datetime(getattr(r, dc), format="%m/%d/%Y", errors="coerce")
        n = getattr(r, nc)
        if pd.isna(d) or pd.isna(n):
            continue
        entries.append((d, str(n).strip(), getattr(r, tc)))
    if not entries:
        continue
    entries.sort(key=lambda e: e[0])
    first = entries[0]
    tim = ""
    for _, n, _ in entries:
        key = " ".join(n.lower().split())
        if key in TIMBER:
            tim = TIMBER[key]
            break
    by_lot[r.OGF_ID] = {"y": int(first[0].year), "t": first[2] if pd.notna(first[2]) else "",
                        "tim": tim}
print(f"patent index: {len(by_lot)} lots with a dated first entry")

# ---------------------------------------------------------------- geometry
to_wgs = Transformer.from_crs("EPSG:3162", "EPSG:4326", always_xy=True).transform

lots = []
years = []
for r in w.itertuples():
    g = r.geom.simplify(SIMPLIFY_M)
    if g.geom_type == "MultiPolygon":
        g = max(g.geoms, key=lambda p: p.area)      # lots are single parcels
    g = transform(to_wgs, g)
    ring = [[round(x, ROUND), round(y, ROUND)] for x, y in g.exterior.coords[:-1]]
    rec = {"r": ring}
    info = by_lot.get(int(r.OGF_ID))
    if info:
        rec["y"] = info["y"]
        if info["t"]:
            rec["t"] = info["t"]
        if info["tim"]:
            rec["tim"] = info["tim"]
        years.append(info["y"])
    lots.append(rec)

xs = [p[0] for lot in lots for p in lot["r"]]
ys = [p[1] for lot in lots for p in lot["r"]]
payload = {
    "meta": {
        "n_lots": len(lots),
        "n_dated": len(years),
        "bounds": [round(min(xs), 3), round(min(ys), 3),
                   round(max(xs), 3), round(max(ys), 3)],
        "source": ("Westmeath lot fabric (Ontario GeoHub, improved) joined to a "
                    "lot-by-lot index of first Crown grants and sales compiled by "
                    "Sam Huckerby from Ontario land records; research materials "
                    "for Clifford & Huckerby (2025)."),
    },
    "lots": lots,
}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(payload, f, separators=(",", ":"), ensure_ascii=False)

byy = pd.Series(years).value_counts().sort_index()
print("first entries by decade:")
print(byy.groupby(byy.index // 10 * 10).sum().to_string())
print(f"timber-connected lots: {sum(1 for l in lots if l.get('tim'))}")
print(f"bounds: {payload['meta']['bounds']}")
print(f"wrote {OUT} ({os.path.getsize(OUT)/1024:.0f} KB)")
