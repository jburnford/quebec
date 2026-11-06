"""Build quebec-arrivals.html from Quebec_All_Data.xlsx.

    python build/make.py

Reads   ../Quebec_All_Data.xlsx, build/template.html, build/coast.json,
        build/inland.json, build/westmeath.json
Writes  ../quebec-arrivals.html   (one self-contained file, no network at runtime)
"""
import pandas as pd
import numpy as np
import json, re, os, io, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "Quebec_All_Data.xlsx")
OUT = os.path.join(ROOT, "quebec-arrivals.html")

OPEN_MONTH, CLOSE_MONTH = 4, 11   # months with traffic; the rest is ice
WINTER_COMPRESS = 8               # off-season days advance this much faster

# ---------------------------------------------------------------- load
df = pd.read_excel(SRC)
n_total = len(df)
df["dt"] = pd.to_datetime(df["FullDate"], errors="coerce")
df["lat"] = pd.to_numeric(df["Latitude"], errors="coerce")
df["lon"] = pd.to_numeric(df["Longitude"], errors="coerce")
df = df[df["dt"].notna() & df["lat"].notna() & df["lon"].notna()].copy()
print(f"kept {len(df)} of {n_total} rows (need a date and origin coordinates)")

# ---------------------------------------------------------------- region
# The Country column follows modern borders and files Belfast/Derry/Newry under
# "United Kingdom". For this period the emigration story is the island's, so
# Ireland is decided geographically instead.
WI = {"Jamaica", "Grenada", "Trinidad and Tobago", "Guyana", "St. Vincent", "Barbados",
      "Antigua and Barbuda", "Saint Kitts and Nevis", "Dominica", "Bahamas", "Bermuda",
      "U.S. Virgin Islands", "Saint Lucia", "Montserrat", "Cuba", "Haiti", "Puerto Rico",
      "Anguilla", "British Virgin Islands", "Belize", "Suriname", "Honduras", "Martinique",
      "Guadeloupe", "Saint Martin", "Turks and Caicos Islands", "Cayman Islands"}
EUR = {"Portugal", "France", "Spain", "Gibraltar", "Germany", "Netherlands", "Belgium",
       "Italy", "Denmark", "Norway", "Sweden", "Russia", "Malta", "Greece", "Poland",
       "Finland", "Estonia", "Latvia", "Lithuania", "Austria", "Switzerland"}


def in_ireland(lat, lon):
    """Island of Ireland. Eastern bound stops west of Wales (Holyhead -4.63);
    western bound keeps transatlantic points out; the last test clips Kintyre."""
    if not (51.2 <= lat <= 55.45 and -10.9 <= lon <= -5.35):
        return False
    if lon >= -6.0 and lat >= 55.3:      # Kintyre, not Antrim
        return False
    return True


def in_scotland(lat, lon):
    """North-west of the border. Piecewise at the head of the Solway (-3.05,54.98):
    east of it the land border climbs to Berwick; west of it the line follows the
    firth out to sea, which keeps Maryport and Workington English."""
    if 54.0 <= lat <= 54.42 and -4.85 <= lon <= -4.30:   # Isle of Man
        return False
    slope = 0.784 if lon >= -3.05 else 0.314
    return lat > 54.98 + slope * (lon + 3.05)


def region(r):
    c, lat, lon = r["Country"], r["lat"], r["lon"]
    if c == "Ireland" or in_ireland(lat, lon):
        return "IE"
    if c in ("United Kingdom", "Jersey", "Guernsey", "Isle of Man"):
        return "SC" if in_scotland(lat, lon) else "EW"
    if c == "Canada":
        return "BNA"
    if c == "United States":
        return "US"
    if c in WI:
        return "WI"
    if c in EUR:
        return "EU"
    return "XX" if pd.isna(c) else "FAR"


df["reg"] = df.apply(region, axis=1)


# ---------------------------------------------------------------- cargo
def cargo_class(v):
    s = "" if pd.isna(v) else str(v).lower()
    if not s.strip():
        return 6
    if "ballast" in s:
        return 0                                    # empty: come for timber
    if re.search(r"\brum|sugar|molasses|coffee|cotton", s):
        return 1
    if re.search(r"\bcoal", s):
        return 2
    if re.search(r"\bsalt\b", s):
        return 3
    if re.search(r"\bfish|oil\b|herring|cod", s):
        return 4
    if re.search(r"dry goods|general|goods|merchandise|wine|iron|brick|stores|provision", s):
        return 5
    return 6


df["cc"] = df["Cargo"].map(cargo_class)


# ---------------------------------------------------------------- names
def titlecase(s):
    small = {"of", "the", "de", "du", "la", "le", "and", "upon", "on", "sur"}
    parts = re.split(r"(\s+|-)", s)
    out = []
    for i, p in enumerate(parts):
        if not p.strip() or p == "-":
            out.append(p)
            continue
        w = p.lower()
        out.append(w if (i > 0 and w in small) else w[:1].upper() + w[1:])
    return "".join(out)


df["port_raw"] = df["From"].map(lambda s: re.sub(r"\s+", " ", "" if pd.isna(s) else str(s).strip()))
df["port_key"] = df["port_raw"].str.lower()

ports = (df.groupby("port_key")
           .agg(name=("port_raw", lambda s: titlecase(s.mode().iat[0])),
                lat=("lat", "median"), lon=("lon", "median"),
                reg=("reg", lambda s: s.mode().iat[0]),
                voyages=("Vessel", "size"),
                settlers=("Number_of_Settlers", "sum"))
           .reset_index().sort_values("voyages", ascending=False).reset_index(drop=True))
pidx = {k: i for i, k in enumerate(ports["port_key"])}
df["pi"] = df["port_key"].map(pidx)

# per-port cargo profile, so Act I can be filtered by trade without replaying
cc_counts = (df.groupby(["pi", "cc"]).size().unstack(fill_value=0)
               .reindex(columns=range(7), fill_value=0)
               .reindex(index=range(len(ports)), fill_value=0))
ports["cc"] = [[int(v) for v in row] for row in cc_counts.to_numpy()]

RIG = r"^(ship|brig|bark|barque|barq|schooner|schr|sloop|snow|bg|s\.?)\b\.?\s*"
RIG_FIX = {"schr": "schooner", "barq": "barque", "bark": "barque",
           "bg": "brig", "s": "ship", "s.": "ship"}


def vessel(v):
    s = re.sub(r"\s+", " ", "" if pd.isna(v) else str(v).strip())
    m = re.match(RIG, s, flags=re.I)
    rig = m.group(1).lower() if m else ""
    nm = re.sub(RIG, "", s, flags=re.I).strip()
    return (titlecase(nm) if nm else titlecase(s)), RIG_FIX.get(rig, rig)


vv = df["Vessel"].map(vessel)
df["vname"] = [a for a, _ in vv]
df["vrig"] = [b for _, b in vv]

# ---------------------------------------------------------------- timeline
D0 = df["dt"].min().date()
df["day"] = (df["dt"].dt.date - D0).map(lambda x: x.days)
DMAX = int(df["day"].max())

vt, t = np.empty(DMAX + 1), 0.0
for i in range(DMAX + 1):
    d = D0 + dt.timedelta(days=i)
    vt[i] = t
    t += 1.0 if OPEN_MONTH <= d.month <= CLOSE_MONTH else 1.0 / WINTER_COMPRESS

# ---------------------------------------------------------------- assemble
df = df.sort_values("day")
voyages = [[int(r.day), int(r.pi), int(r.Number_of_Settlers), int(r.cc)]
           for r in df.itertuples()]

df["yr"] = df["dt"].dt.year
yearly = []
for y, g in df.groupby("yr"):
    yearly.append({
        "y": int(y),
        "voyages": int(len(g)),
        "settlers": int(g["Number_of_Settlers"].sum()),
        "ships_with_settlers": int((g["Number_of_Settlers"] > 0).sum()),
        "reg": {k: int(v) for k, v in
                g.groupby("reg")["Number_of_Settlers"].sum().to_dict().items() if v > 0},
    })

days = pd.to_numeric(df["Sailed"].astype(str).str.extract(r"(\d+)\s*days?", flags=re.I)[0],
                     errors="coerce")

payload = {
    "meta": {
        "d0": D0.isoformat(), "dmax": DMAX, "vtmax": float(t),
        "rows_total": int(n_total), "rows_used": int(len(df)),
        "settlers_total": int(df["Number_of_Settlers"].sum()),
        "passage": {"n": int(days.notna().sum()), "median": float(days.median()),
                    "p10": float(days.quantile(.10)), "p90": float(days.quantile(.90))},
        "quebec": [46.8139, -71.2080],
        # plain text: the page escapes these where it builds markup
        "cargo_labels": ["In ballast", "Rum & sugar", "Coals", "Salt",
                         "Fish & oil", "Goods", "Other"],
    },
    "vt": [round(float(x), 3) for x in vt],
    "ports": [{"name": p["name"], "lat": round(float(p["lat"]), 3),
               "lon": round(float(p["lon"]), 3), "reg": p["reg"],
               "voyages": int(p["voyages"]), "settlers": int(p["settlers"]),
               "cc": p["cc"]}
              for p in ports.to_dict("records")],
    "voyages": voyages,
    # vessel names/rigs are parsed above but not shipped: nothing in the page
    # uses them since the arrivals ticker was removed, and they cost ~300 KB.
    "yearly": yearly,
}

tpl = io.open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
sub = {
    "/*__DATA__*/": json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
    "/*__COAST__*/": io.open(os.path.join(HERE, "coast.json"), encoding="utf-8").read(),
    "/*__INLAND__*/": io.open(os.path.join(HERE, "inland.json"), encoding="utf-8").read(),
    "/*__WESTMEATH__*/": io.open(os.path.join(HERE, "westmeath.json"), encoding="utf-8").read(),
    "/*__HYDRO__*/": io.open(os.path.join(HERE, "hydro.json"), encoding="utf-8").read(),
    "/*__TIMBER__*/": io.open(os.path.join(HERE, "timber.json"), encoding="utf-8").read(),
}
for token, value in sub.items():
    assert token in tpl, f"missing token {token} in template.html"
    tpl = tpl.replace(token, value)

io.open(OUT, "w", encoding="utf-8").write(tpl)

print(f"\nsettlers total   {payload['meta']['settlers_total']:,}")
print("by region        " + "  ".join(
    f"{k} {v:,}" for k, v in sorted(
        df.groupby('reg')['Number_of_Settlers'].sum().items(), key=lambda x: -x[1]) if v))
print(f"\nwrote {OUT}  ({os.path.getsize(OUT)/1024:.0f} KB)")
