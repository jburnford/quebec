# A Cheap Bridge — The Port of Quebec, 1817–1839

An animated public-history visualization of the Quebec Arrivals Database: every
vessel recorded arriving at the Port of Quebec between 10 May 1817 and
20 November 1839, and what the traffic meant.

**[`quebec-arrivals.html`](quebec-arrivals.html)** is the whole piece — one
self-contained file. Open it in any browser. No server, no build step, no
network access at runtime.

## The three acts

| | | |
|---|---|---|
| **I · The Port** | *Static.* All 17,062 mapped arrivals at once — the geography of the port's trade, each origin sized by voyages and coloured by the trade it mostly served. Filter to one cargo to isolate that run | from the database |
| **II · The Crossing** | *Animated.* The same seasons, showing only ships carrying settlers. Each dot is one vessel in passage along its sea lane, its area proportional to the people aboard | from the database |
| **III · Beyond the Rapids** | *Animated.* Where the crossing led — and it did not lead to one place. Ends in Westmeath Township, where the actual survey fabric fills lot by lot as land passes into private hands, against the arc of the Algonquin petitions | from Clifford & Huckerby (2025) and its research materials |

Act I is deliberately not a ship-by-ship animation. Its subject is structure, not
sequence: three overlapping systems — a North Atlantic run to Britain and
Ireland, a Caribbean run carrying produce north, and a coastal run from the Gulf
and the Maritimes — which are far easier to read all at once than in transit.

Act III opens by making clear that **Quebec was a landing place, not a
destination**. Most arrivals pushed on into Upper Canada; others took up land in
the Eastern Townships; many thousands crossed into the United States. The act
then follows *one* of those routes — the Ottawa Valley — as a case study,
because that is where timber extraction and settlement are most tightly bound
together. The other corridors stay drawn on the map throughout so the valley
never reads as the whole story.

The act carries the article's central argument in parallel: the Algonquin and
Nipissing chiefs asserted their ownership from 1791 onward and were repeatedly
put off — Darling's agriculture-only terms in 1827, Colborne's 1835
undertaking on an Allumette Island reserve, Bond Head's reversal a year
later, and the Bagot Commission's 1845 finding that ~800 squatters had
already foreclosed the reserve. The Westmeath close-up makes the "dialectic of
policy and practice" visible: the township's real survey fabric appears with
the 1832 surveys and fills lot by lot from the land patent index while those
reversals happen — every lot sold a fact on the ground against the reserve.
Holdings of the men the article documents in both farming and timber (Egan,
Carmichael, Bellows, Adams, Tucker) light up at the "oats and hay" beat. The
act ends with the ongoing modern treaty negotiation and Greg Sarazin's words.

The hinge between Acts I and II is the record's central finding. Of the 8,955
vessels that declared no cargo at all — arriving *in ballast*, having crossed
the Atlantic empty to load timber — those same ships landed **203,816 settlers,
61% of everyone in the database**. Nathaniel Gould told Parliament in 1833 that
the lumber vessels going out in ballast made "a CHEAP BRIDGE… for the passage of
Emigrants." The arrivals record shows he was right.

Act III leaves the spreadsheet behind and is labelled as such throughout: the
newspapers logged each vessel as it reached the quay and then stopped.

## Headline figures

| | |
|---|---|
| Arrivals mapped | 17,062 of 17,879 rows |
| Settlers landed | 331,839 |
| Origin ports | 527, geocoded |
| Ireland / England & Wales / Scotland | 214,507 / 73,997 / 38,024 |
| Peak season | 1832 — 45,247 settlers |
| Collapse | 1838 — 2,790, after the Rebellions |
| Median passage | 40 days (2,900 voyages state a duration) |

## Rebuilding

```bash
python build/make.py
```

Requires `pandas` and `openpyxl`. Reads `Quebec_All_Data.xlsx` plus the four
committed basemap/data files, and writes `quebec-arrivals.html`.

To regenerate the basemaps from Natural Earth (only needed if you change the map
windows — it downloads ~3 MB and caches it in `build/_ne_cache/`):

```bash
python build/basemap.py
```

`build/westmeath.json` and `build/hydro.json` are committed too, so `make.py`
never needs the sources below. To regenerate them:

- `python build/westmeath.py` reads the Westmeath lot fabric and the land
  patent index from the HGIS Lab share (`G:`); requires `pyogrio`, `shapely`,
  `pyproj`.
- `python build/hydro.py` fetches upper-Ottawa water polygons from OpenStreetMap
  via Overpass (cached in `build/_osm_cache/`); requires `shapely`.

| File | What it is |
|---|---|
| `build/make.py` | Data preparation and assembly |
| `build/template.html` | Markup, styling and the animation engine |
| `build/basemap.py` | Fetches Natural Earth, clips and simplifies |
| `build/coast.json` | Atlantic coastline, 110m, 26 rings |
| `build/inland.json` | St Lawrence–Ottawa land, lakes and rivers, 50m |
| `build/westmeath.py` | Exports the lot fabric + patent index from the lab share |
| `build/westmeath.json` | 538 Westmeath lots; 215 dated first grants/sales; timber flags |
| `build/hydro.py` | Fetches and simplifies OSM water for the upper Ottawa |
| `build/hydro.json` | River, lakes and 46 islands, ~50 m resolution, ODbL |

## Decisions worth knowing about

**Origin regions are geographic, not modern-national.** The source file's
`Country` column follows present-day borders and files Belfast, Londonderry and
Newry under "United Kingdom". Since the whole point of Act II is where people
sailed from, `Ireland` here means the island of Ireland. Scotland is divided
from England & Wales along the Solway–Tweed line, applied piecewise at the head
of the Solway so the Cumbrian ports stay English. Both tests are in
`build/make.py`; both were checked against a list of 44 known ports.

**Winter is compressed 8:1** on the timeline. Almost nothing arrives between
December and March because the St Lawrence is frozen, and at true scale the
animation would spend a third of its length on an empty river.

**Routes follow sea lanes, and they are plausible rather than surveyed.** Ships
did not fly over Ireland, so routes are not straight lines or arcs. Every voyage
in this record converges on the same funnel — round Newfoundland, through the
Cabot Strait, up the Gulf and the river — so the map is built from one shared
trunk plus about fifteen approach lanes (Irish Sea, North Channel, Channel,
Bristol Channel, Thames, North Sea, Iberia, two Caribbean branches either side
of the Antilles, and so on), with each port assigned to a lane geographically.
Waypoints were placed by hand in open water and checked by point-in-polygon
against the coastline: **land crossings fall from 100% of voyages on straight
lines to 8.6%**, and what remains is almost entirely the final hop to ports that
genuinely sit inland — Gloucester up the Severn, Bordeaux up the Gironde,
Newcastle up the Tyne. No track survives for individual voyages, so these are a
reasonable reconstruction of where ships went, not evidence of it.

In Act II each dot leaves its origin 40 days before the recorded arrival — the
median passage in this database. The inland corridors in Act III are schematic in
the same way and carry no counts: the database records nothing past the quay.

**The Westmeath sequence is drawn from real parcels.** The grid is the
township's improved lot fabric (Ontario GeoHub); each lot's tint year is the
earliest dated entry in a lot-by-lot index of Crown grants and sales compiled
by Sam Huckerby from Ontario land records. 215 of 538 lots have a dated entry,
so the fill *understates* ownership — the article finds nearly every lot owned
by 1852. A dozen entries are paper grants from 1817–21 (militia and Loyalist
rights), years before any settler arrived. Timber-connected holdings are
matched by name and can miss holdings recorded under other names. Water at
that zoom (the river, lakes, Allumette and the Rocher Fendu islands) is
OpenStreetMap, simplified to ~50 m, fading in as Natural Earth fades out. The
dashed ellipse over Allumette Island marks a position, not a boundary — no
reserve boundary survives to draw.

**817 rows are not mapped** because they lack a usable date or origin
coordinate, so totals here run slightly below the full spreadsheet (the article
reports 334,126 settlers across 17,783 records).

**Some geocoding in the source is wrong.** "St Laurence, Nfld" resolves to
Texas and "Esquimault Bay" to Vancouver Island. These plot at the map edge
rather than being silently dropped.

**Merchants are deliberately not charted.** The article's Figure 4 finds the top
twenty Quebec merchants received 54% of all settlers, and that thirty-nine of the
top forty shipped timber. Reproducing that needs the authors' own consolidation
of naming variants in the `Merchant` column — a naïve grouping treats "to order"
as a firm and splits Pemberton across three spellings. The finding is cited in
the notes panel instead.

**Settler counts are not a complete emigration series.** They are transcribed
from newspaper arrival notices; many vessels carried passengers the notice never
enumerated.

## Accessibility

Legend always present; a full data table of all 23 seasons plus sources and
caveats behind **Data & notes**; keyboard control (space, arrow keys); the
categorical palette validated for colour-vision deficiency, lightness band,
chroma and contrast against the map surface; `prefers-reduced-motion` respected
(the piece loads at its end state and waits).

## Sources

- **Quebec Arrivals Database**, transcribed from the *Quebec Gazette /
  Gazette de Québec* 1817–1839 and theshipslist.com.
  doi:[10.5281/zenodo.15068764](https://doi.org/10.5281/zenodo.15068764)
- Jim Clifford and Sam Huckerby, "Logging and Settlement beyond the Rapids:
  Unmaking Algonquin Space in the Ottawa Valley, 1817–61," *Canadian Historical
  Review* 106, no. 3 (September 2025).
  doi:[10.3138/chr-2024-0055](https://doi.org/10.3138/chr-2024-0055)
- Nathaniel Gould, *Sketch of the Trade of British America* (London, 1833), 10.
- Westmeath lot fabric: Ontario GeoHub (improved lot fabric), joined to a land
  patent index compiled by Sam Huckerby from Ontario land records (research
  materials for the article above).
- Basemaps: [Natural Earth](https://www.naturalearthdata.com/), public domain;
  upper-Ottawa water polygons © [OpenStreetMap](https://www.openstreetmap.org/copyright)
  contributors, ODbL.
