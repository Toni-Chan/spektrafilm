# FUJIFILM motion picture camera negatives — raw curve records

Source: FUJIFILM / Fuji Photo Film motion picture data sheets (KB-series brochures,
1999-2009) and the *FUJIFILM Motion Picture Film* manual KB-1101E (2011), as mirrored
on the web (each record's `info.txt` names the sheet, its reference number / print
code and the PDF URL; the PDFs are not redistributed here). None of these sheets is
catalogued by filmcolors.org. Page numbers are PDF pages.

The curves are digitised with
[`scripts/extract_filmcolors_datasheets.py`](../../../../../scripts/extract_filmcolors_datasheets.py)
(`--raw` pointing at this folder), from the per-sheet configs `sheets/<ref>.json`
(stock metadata, caveats, builder recipe). The brochures are A3 spreads stored as
rotated portrait pages (`"derotate": true`); most carry their curves as vector art
and are read straight from the PDF paths, ETERNA Vivid 500 (KB-0901E) is one
embedded ~150 dpi colour image and is traced colour by colour. The written curves
lie within 1 pt (95th percentile) of the printed strokes (`extraction_summary.json`);
the overlay check images come from the script (`--checks`) and are not committed.

The ETERNA / Vivid / REALA brochures and the manual print the characteristic curves
against **camera stops** (−6…+6 around normal exposure); they are written as relative
log H (1 stop = 0.30103), the absolute exposure scale coming from the builder's
speed-point anchoring. The F-series sheets and the manual's F-64D / REALA 500D pages
use log H (bar notation). Sensitivities are defined at density 0.40 above D-min
(`log_sensitivity_density_over_min` 0.4), densitometry Status M, process ECN-2.

The manual prints characteristic curves only. ETERNA 250, ETERNA 400, F-64D and
REALA 500D therefore take their spectral sensitivities and dye densities from a
sibling record (`"borrow"`, listed in `info.txt`, `extraction_summary.json` and the
profile datasource as estimates) and are built with a lower `data_trustability`.

`records.csv` lists the records, `recipes.csv` is the batch recipe the profiles were
built from:

```bash
spektrafilm-profile-builder batch \
    src/spektrafilm_profile_builder/data/raw/fujifilm_motion_picture_data_sheets/recipes.csv \
    -o src/spektrafilm/data/profiles
```

| record / profile | sheet | date | art | notes |
|---|---|---|---|---|
| `fujifilm_eterna_250d_kb0507er` | ETERNA 250D 8563/8663, KB-0507ER, p. 1 | 2007-05 | vector | daylight; camera-stop axis |
| `fujifilm_eterna_vivid_160_kb0701e` | ETERNA Vivid 160 8543/8643, KB-0701E, p. 1 | 2007-03 | vector | tungsten; high-saturation stock |
| `fujifilm_eterna_vivid_500_kb0901e` | ETERNA Vivid 500 8547/8647, KB-0901E, p. 1 | 2009-04 | raster | tungsten; colour-masked tracing |
| `fujifilm_f250_kb914e` | F-250 8552/8652, KB-914E, p. 1 | 2000-05 | vector | tungsten; Super F series |
| `fujifilm_f125_kb913e` | F-125 8532/8632, KB-913E, p. 1 | 1999-05 | vector | tungsten; Super F series |
| `fujifilm_eterna_250_kb1101e` | ETERNA 250 8553/8653, KB-1101E, p. 10 | 2011-02 | vector | char only; sensitivities / dyes borrowed from F-250 |
| `fujifilm_eterna_400_kb1101e` | ETERNA 400 8583/8683, KB-1101E, p. 12 | 2011-02 | vector | char only; borrowed from ETERNA Vivid 500 |
| `fujifilm_f64d_kb1101e` | F-64D 8522/8622, KB-1101E, p. 18 | 2011-02 | vector | char only; borrowed from ETERNA 250D |
| `fujifilm_reala_500d_kb1101e` | REALA 500D 8592/8692, KB-1101E, p. 24 | 2011-02 | vector | char only; borrowed from ETERNA 250D (fourth layer not modelled) |

Estimates common to all (also in each profile's datasource): sensitivity tails beyond
the printed curves, the individual CMY dyes (reconstructed by the builder from the
mid-scale and minimum densities), dye densities outside 400-700 nm, the print stock
(KODAK VISION 2383; FUJIFILM ETERNA-CP is not in the repository), the hanatos2025
adaptation parameters (pinned Fujifilm negative donors) and the interlayer DIR
coupler strength.
