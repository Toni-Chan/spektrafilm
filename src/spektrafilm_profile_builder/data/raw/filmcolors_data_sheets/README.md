# filmcolors.org data sheets — raw curve records

Source: data sheets and product information bulletins catalogued by the
**Timeline of Historical Film Colors** (filmcolors.org, University of Zurich,
<https://filmcolors.org/cat/Data-sheets/>). Each record's `info.txt` names the
sheet, its print code / date, the PDF URL and the catalogue entry; the PDFs are
not redistributed here. Page numbers are PDF pages.

Some of these sheets carry their curves as embedded scans with the axis
labels inside the bitmap, so the vector readers used for the Fujifilm Data
Guide and the KODAK E-series sheets do not apply. They are digitised with
[`scripts/extract_filmcolors_datasheets.py`](../../../../../scripts/extract_filmcolors_datasheets.py):
the plot is rendered at 600 dpi, the grid lines are removed except where a
curve crosses them, the axes are calibrated piecewise-linearly through the
printed grid lines, and each curve is followed from seed points given in the
per-sheet config `sheets/<ref>.json` (which also holds the stock metadata, the
caveats and the builder recipe); a slightly tilted scan is deskewed first
(`rotate`). Sheets whose curves are vector art are read straight from the PDF
paths with the same calibration.
The written curves lie within 1 pt (95th percentile; vector sheets exactly) of the printed
strokes (`extraction_summary.json`); the overlay check images are produced by
the script (`--checks`) and are not committed.

`records.csv` lists the records, `recipes.csv` is the batch recipe the
profiles were built from:

```bash
spektrafilm-profile-builder batch \
    src/spektrafilm_profile_builder/data/raw/filmcolors_data_sheets/recipes.csv \
    -o src/spektrafilm/data/profiles \
    --filters-json src/spektrafilm/data/filters/neutral_print_filters.json
```

| record / profile | sheet | date | art | notes |
|---|---|---|---|---|
| `fujifilm_super_hg_1600_af3659en` | FUJICOLOR SUPER HG 1600 CU, AF3-659EN, pp. 5-7 | undated (ca. 1990) | scans | char and dye plots deskewed (-0.5 / +0.2 deg); CN-16 |
| `fujifilm_npc_160_af3065e` | FUJICOLOR NPC 160 PROFESSIONAL [NPC], AF3-065E, p. 5 | 2001-01 | vector | fourth (cyan-sensitive) layer kept as `log_sensitivity_cyan_layer.csv` |
| `fujifilm_nps_160_af3809e` | FUJICOLOR NPS 160 PROFESSIONAL [NPS], AF3-809E, p. 4 | 1999-01 | scans | dashed fourth-layer curve not traced |
| `fujifilm_nph_400_af3121e` | FUJICOLOR PORTRAIT FILM NPH 400 PROFESSIONAL [NPH], AF3-121E, p. 8 | 2002-07 | vector | the newer NPH edition; fourth layer kept as a record file |
| `fujifilm_nph_400_af3865e` | FUJICOLOR NPH 400 PROFESSIONAL [NPH], AF3-865E, p. 6 | 1995-07 | scans | **record only** (older emulsion); not built |
| `fujifilm_npz_800_af3100e` | FUJICOLOR PORTRAIT FILM NPZ 800 PROFESSIONAL [NPZ], AF3-100E, p. 5 | 2001-04 | scans | |
| `fujifilm_pro_160ns_af30232e` | FUJICOLOR PRO 160 NS PROFESSIONAL, AF3-0232E, p. 7 | 2010-03 | vector | fourth layer kept as a record file |
| `fujifilm_nexia_h400_af3013e` | FUJICOLOR nexia H 400 [APS], AF3-013E, p. 5 | 1998-10 | vector | fourth layer kept as a record file; dye plot to 780 nm |

## Estimate placeholders

Everything a sheet does not print is an estimate, listed in each recipe's
`datasource` (and so in the profile's `metadata.datasource`):

- the individual cyan / magenta / yellow dye densities: the sheets print only
  the mid-scale neutral and minimum densities, the builder reconstructs the
  three dyes (and the base + fog) from them;
- the absolute sensitivity level: the sheets give relative log sensitivity
  (one log unit = the interval marked "1.0"), the builder anchors it at mid
  grey;
- sensitivity tails beyond the printed curves;
- the hanatos2025 adaptation parameters, averaged from the pinned
  `adaptation_donors` (shipped Fujifilm colour negative profiles);
- interlayer DIR coupler strength: the runtime default for negatives, except
  NPC (`src/spektrafilm/data/film_render_overrides/fujifilm_npc_160_af3065e.json`,
  scale 1.35, `"estimate": true`), which from its curves alone rendered below
  NPS although FUJIFILM sells it as the more saturated, higher-contrast
  sibling;
- target print `fujifilm_crystal_archive_typeii`, reference illuminant D55.

The fourth (cyan-sensitive, "4th colour layer") curve printed on the later
sheets is kept as an extra record file; spektrafilm models three layers, so it
is not used. `neutral_print_filters.json` holds fitted neutral enlarger filters
for every print paper.

The data are FUJIFILM's; they are included, like the other data-sheet data
spektrafilm is built on, as measurements digitised from publicly published
technical documents, with attribution, for simulation purposes.
