# filmcolors.org data sheets — raw curve records

Source: data sheets and product information bulletins catalogued by the
**Timeline of Historical Film Colors** (filmcolors.org, University of Zurich,
<https://filmcolors.org/cat/Data-sheets/>). Each record's `info.txt` names the
sheet, its print code / date, the PDF URL and the catalogue entry; the PDFs are
not redistributed here. Page numbers are PDF pages.

Most of these sheets carry their curves as embedded 1-bit scans with the axis
labels inside the bitmap, so the vector readers used for the Fujifilm Data
Guide and the KODAK E-series sheets do not apply. They are digitised with
[`scripts/extract_filmcolors_datasheets.py`](../../../../../scripts/extract_filmcolors_datasheets.py):
the plot is rendered at 600 dpi, the grid lines are removed except where a
curve crosses them, the axes are calibrated piecewise-linearly through the
printed grid lines, and each curve is followed from seed points given in the
per-sheet config `sheets/<ref>.json` (which also holds the stock metadata, the
caveats and the builder recipe). Sheets whose curves are vector art (T64,
PROVIA 400X) are read straight from the PDF paths with the same calibration.
The written curves lie within about 0.5 pt (95th percentile) of the printed
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
| `fujifilm_provia_100_rdp2_af3796e` | FUJICHROME PROVIA 100 Professional [RDP II], AF3-796E, p. 6 | 1996-04 | 1-bit scans | |
| `fujifilm_provia_1600_rsp_af3798e` | FUJICHROME PROVIA 1600 Professional [RSP], AF3-798E, p. 6 | 1994-01 | 1-bit scans | EI 1600 (ISO 400 pushed +2); crossed channel curves |
| `fujifilm_ms_100_1000_rms_af3989e` | FUJICHROME MS 100/1000 Professional [RMS], AF3-989E, p. 6 | 1998-06 | 1-bit scans (+ vector sens) | EI 100 curve set only (EI 400 / 800 not extracted) |
| `fujifilm_t64_rtp_af3178e` | FUJICHROME T64 Professional [RTP], AF3-178E, p. 7 | 2005-09 | vector | tungsten 3200 K (reference illuminant T) |
| `fujifilm_provia_400x_rxp_af30213e` | FUJICHROME PROVIA 400X Professional [RXP], AF3-0213E, p. 7 | 2006-01 | vector | |
| `fujifilm_velvia_50_rvp50_af30221e2` | FUJICHROME Velvia 50 Professional [RVP50], AF3-0221E2, p. 8 | 2007-03 | 1-bit scans | the 2007 reissue; `fujifilm_velvia_50_fdg` is the original RVP |

## Estimate placeholders

Everything a sheet does not print is an estimate, listed in each recipe's
`datasource` (and so in the profile's `metadata.datasource`):

- dye densities outside the printed wavelength range (`dye_extension
  hold_decay`: held on the short side, exponential decay on the long side);
- sensitivity tails beyond the printed curves;
- the hanatos2025 adaptation parameters, averaged from the pinned
  `adaptation_donors` (shipped Fujifilm reversal profiles);
- interlayer DIR coupler strength: per-stock
  `src/spektrafilm/data/film_render_overrides/<stock>.json` where the
  ColorChecker chroma from the sheet alone clearly misses the film's known
  character (PROVIA 100 RDP II 1.4, MS 100/1000 1.8, Velvia 50 2007 1.6; all
  marked `"estimate": true`);
- T64: neutral balance assumed under 3200 K tungsten although its curve plot is
  captioned "Dayloght" (sic).

The data are FUJIFILM's; they are included, like the other data-sheet data
spektrafilm is built on, as measurements digitised from publicly published
technical documents, with attribution, for simulation purposes.
