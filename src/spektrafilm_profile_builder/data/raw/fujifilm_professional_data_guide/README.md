# Fujifilm Professional Data Guide — raw curve records

Source: **FUJIFILM Professional Data Guide**, AF3-207U (2005), published by
FUJIFILM Corporation: <https://asset.fujifilm.com/www/us/files/2020-03/3ab271f46f8d71c7e4c91bcedb7de050/ProfessionalFilmDataGuide.pdf>
(PDF not redistributed here). Page numbers below are PDF pages.

The curves were read from the vector strokes of the PDF (not traced from
bitmaps) with [`scripts/extract_fujifilm_data_guide.py`](../../../../../scripts/extract_fujifilm_data_guide.py);
axes are calibrated from the printed tick labels snapped to the grid. Typical
accuracy is 0.1-0.2 pt on the page (about 0.5-1 nm, 0.005-0.01 log H,
0.005-0.01 density) on top of the accuracy of the original drawing. Each
folder's `info.txt` lists the speed, process, densitometry, calibration
residuals and caveats; `extraction_summary.json` collects the same for all
records, `index.csv` lists them, and `recipes.csv` is the batch recipe the
`*_fdg` profiles were built from (`spektrafilm-profile-builder batch recipes.csv`).

The data are FUJIFILM's; they are included, like the other data-sheet data
spektrafilm is built on, as measurements digitised from a publicly published
technical document, with attribution, for simulation purposes.

| record | name in the guide | PDF page | type | profile |
|---|---|---|---|---|
| `positive/fujifilm_velvia_50` | FUJICHROME Velvia for Professionals [RVP] (Velvia 50) | 24 | positive | `fujifilm_velvia_50_fdg` |
| `positive/fujifilm_velvia_100` | FUJICHROME Velvia 100 Professional [RVP100] | 24 | positive | `fujifilm_velvia_100_fdg` |
| `positive/fujifilm_velvia_100f` | FUJICHROME Velvia 100F Professional [RVP100F] | 25 | positive | `fujifilm_velvia_100f_fdg` |
| `positive/fujifilm_provia_100f` | FUJICHROME PROVIA 100F Professional [RDPIII] | 25 | positive | `fujifilm_provia_100f_fdg` |
| `positive/fujifilm_astia_100f` | FUJICHROME ASTIA 100F Professional [RAP100F] | 26 | positive | `fujifilm_astia_100f_fdg` |
| `positive/fujifilm_provia_400f` | FUJICHROME PROVIA 400F Professional [RHPIII] | 26 | positive | `fujifilm_provia_400f_fdg` |
| `positive/fujifilm_64t_type_ii` | FUJICHROME 64T TYPE II Professional [RTPII] | 27 | positive | `fujifilm_64t_type_ii_fdg` |
| `positive/fujifilm_sensia_100` | FUJICHROME Sensia 100 [RA] | 27 | positive | `fujifilm_sensia_100_fdg` |
| `positive/fujifilm_sensia_200` | FUJICHROME Sensia 200 [RM] | 28 | positive | `fujifilm_sensia_200_fdg` |
| `positive/fujifilm_sensia_400` | FUJICHROME Sensia 400 [RH] | 28 | positive | `fujifilm_sensia_400_fdg` |
| `negative/fujifilm_pro_160s` | FUJICOLOR PRO 160S PROFESSIONAL [PRO 160S] | 29 | negative | `fujifilm_pro_160s_fdg` |
| `negative/fujifilm_pro_160c` | FUJICOLOR PRO 160C PROFESSIONAL [PRO 160C] | 29 | negative | `fujifilm_pro_160c_fdg` |
| `negative/fujifilm_npl_160` | FUJICOLOR NPL 160 PROFESSIONAL [NPL] | 30 | negative | `fujifilm_npl_160_fdg` |
| `negative/fujifilm_pro_400h` | FUJICOLOR PRO 400H PROFESSIONAL [PRO 400H] | 30 | negative | `fujifilm_pro_400h_fdg` |
| `negative/fujifilm_pro_800z` | FUJICOLOR PRO 800Z PROFESSIONAL [PRO 800Z] | 31 | negative | `fujifilm_pro_800z_fdg` |
| `negative/fujifilm_superia_reala` | FUJICOLOR SUPERIA REALA [CS] | 31 | negative | `fujifilm_superia_reala_fdg` |
| `negative/fujifilm_superia_100` | FUJICOLOR SUPERIA 100 [CN] | 32 | negative | `fujifilm_superia_100_fdg` |
| `negative/fujifilm_superia_200` | FUJICOLOR SUPERIA 200 [CA] | 32 | negative | `fujifilm_superia_200_fdg` |
| `negative/fujifilm_superia_xtra_400` | FUJICOLOR SUPERIA X-TRA 400 [CH] | 33 | negative | `fujifilm_superia_xtra_400_fdg` |
| `negative/fujifilm_press_400` | FUJICOLOR PRESS 400 [CH] | 33 | negative | — (same data as `fujifilm_superia_xtra_400`) |
| `negative/fujifilm_true_definition_400` | FUJICOLOR TRUE DEFINITION 400 [CH] | 33 | negative | `fujifilm_true_definition_400_fdg` |
| `negative/fujifilm_superia_xtra_800` | FUJICOLOR SUPERIA X-TRA 800 [CZ] | 34 | negative | `fujifilm_superia_xtra_800_fdg` |
| `negative/fujifilm_press_800` | FUJICOLOR PRESS 800 [CZ] | 34 | negative | — (same data as `fujifilm_superia_xtra_800`) |
| `negative/fujifilm_superia_1600` | FUJICOLOR SUPERIA 1600 [CU] | 34 | negative | `fujifilm_superia_1600_fdg` |
| `bw/fujifilm_neopan_acros_100` | NEOPAN 100 ACROS | 40 | bw | — (B&W, not built) |
| `bw/fujifilm_neopan_400` | NEOPAN 400 Professional | 41 | bw | — (B&W, not built) |
| `bw/fujifilm_neopan_1600` | NEOPAN 1600 Professional | 42 | bw | — (B&W, not built) |
| `negative/fujifilm_nexia_a200` | FUJICOLOR nexia A200 [DA] (APS) | 53 | negative | `fujifilm_nexia_a200_fdg` |
| `negative/fujifilm_nexia_400` | FUJICOLOR nexia 400 [DH] (APS) | 53 | negative | `fujifilm_nexia_400_fdg` |
| `negative/fujifilm_nexia_800` | FUJICOLOR nexia 800 [DZ] (APS) | 54 | negative | `fujifilm_nexia_800_fdg` |

## What is in a record

* Reversal (FUJICHROME): `log_sensitivity_{r,g,b}`, `dye_density_{c,m,y}`
  (the guide prints the three dyes separately), `density_curve_{r,g,b}`
  (status A, total density), `mtf`.
* Negative (FUJICOLOR): `log_sensitivity_{r,g,b}`, `log_sensitivity_cyan_layer`
  (Fuji's 4th, cyan-sensitive inhibitor layer; kept here as raw data only:
  it is not merged into the red sensitivity and not written to the profiles,
  since upstream's profile loader rejects unknown keys), `dye_density_{mid,min}` (mid-scale neutral and
  minimum spectral densities; the guide does not separate C/M/Y for negatives,
  so the builder reconstructs them), `density_curve_{r,g,b}` (status M, total
  density), `mtf`.
* B&W (NEOPAN): `log_sensitivity` and one `density_curve_*` per published D-76
  development time and film size (`density_curve.csv` = the middle time).

## Caveats

* Negative sensitivity charts print a 1.0 log-unit scale bracket but no axis
  numbers, so the sensitivity zero point is relative (R, G, B share it). The
  profile builder normalises sensitivities on a mid-grey exposure, so the
  zero point does not matter for the profiles.
* Where the reversal R/G/B characteristic curves overlap, the PDF draws a
  single solid (red) line; G and B use it outside their own dashed traces
  (see each `info.txt`).
* PRESS 400 and PRESS 800 share the pages (and data) of SUPERIA X-TRA 400 and
  800. Their folders are kept for completeness; no separate profiles are built
  because the profile format has no alias mechanism and the files would be
  identical.
* Cross-check against the raw data upstream used before it moved them out of
  the repository (`a6dbcfd^`): X-TRA 400, PRO 400H and Velvia 100 agree to
  within ~0.01-0.04 (log sensitivity / density RMS); Provia 100F's green
  sensitivity peak sits on the other of its two maxima (575 vs 547 nm),
  which suggests the upstream data came from a different sheet revision.
* The B&W records are not turned into profiles: the profile schema has a
  `channel_model: bw` value but the runtime has no B&W film or silver-paper
  path yet.
