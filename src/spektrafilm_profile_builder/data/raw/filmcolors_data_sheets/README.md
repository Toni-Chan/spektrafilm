# filmcolors.org data sheets — raw curve records

Source: data sheets and product information bulletins catalogued by the
**Timeline of Historical Film Colors** (filmcolors.org, University of Zurich,
<https://filmcolors.org/cat/Data-sheets/>). Each record's `info.txt` names the
sheet, its print code / date, the PDF URL and the catalogue entry; the PDFs are
not redistributed here. Page numbers are PDF pages.

The sheets are digitised with
[`scripts/extract_filmcolors_datasheets.py`](../../../../../scripts/extract_filmcolors_datasheets.py)
(see its docstring): raster plots are rendered at 600 dpi and each curve is
followed from seed points in the per-sheet config `sheets/<ref>.json` (which
also holds the stock metadata, the caveats and the builder recipe); vector
curves are read straight from the PDF paths with the same calibration.
`extraction_summary.json` gives the distance of every written curve to the
printed strokes; the overlay check images (`--checks`) are not committed.
`records.csv` lists the records, `recipes.csv` is the batch recipe.

## KODAK reversal sheets

| record | sheet | pages | art | profile |
| --- | --- | --- | --- | --- |
| `positive/kodak_ektachrome_eir_ti2323` | TI-2323 (September 2005) KODAK EKTACHROME Professional Infrared EIR Film | 7-8 | vector | `kodak_ektachrome_eir_ti2323` |
| `positive/kodak_ektachrome_100d_h15294` | H-1-5294 (2019, revised 5-24) KODAK EKTACHROME 100D Color Reversal Film 5294 / 7294 | 3-4 | raster (JPEG) | `kodak_ektachrome_100d_h15294` |

### EKTACHROME Infrared EIR (TI-2323)

A false-colour reversal film: its green-, red- and infrared-sensitive layers
form yellow, magenta and cyan dye. spektrafilm names layers by the dye they
form, so the record puts the green-sensitive (yellow-forming) layer in `b`,
the red-sensitive (magenta-forming) layer in `g` and the infrared-sensitive
(cyan-forming) layer in `r`; the characteristic curves are assigned by the
label printed at each curve's start (Blue/Green, Green/Red, Red/IR). The
sensitivities are printed from 400 to 900 nm; what spektrafilm can model:

* the visible part of the false-colour mapping (green subjects lose yellow
  dye and go blue, red subjects go green), with the blue sensitivity of all
  three layers as printed (the sheet recommends a No. 12 yellow filter, which
  the profile does not include);
* **not** the infrared response: spektrafilm's spectral grid and its RGB-to-
  spectrum input stop in the visible / near infrared, so the infrared-
  sensitive layer only sees the tail of its sensitivity there, and foliage
  does not turn red as on the real film.

Process AR-5 curves (E-6 gives higher contrast and saturation, per the
sheet). The `400` x label of the dye plot is not separate text; the x axis is
calibrated from the 500-700 nm labels.

### EKTACHROME 100D 5294 / 7294 (H-1-5294)

The PDF is images only (no text layer). The colour curves cross each other,
so each is traced only through pixels of its printed colour (`rgb` in the
config). The sensitometry plot's top axis (log lux-seconds) is used; the
printed dyes are peak-normalised (note on the sheet), the black curve is the
midscale neutral. The density at which sensitivity is defined is not stated
(1.0 assumed, as on the other KODAK reversal sheets).

### Estimates (also in each profile's `metadata.datasource`)

Dye densities outside the printed 400-700 nm (`hold_decay`), sensitivity
tails beyond the printed curves, the hanatos2025 adaptation parameters
(donors pinned to upstream's and the KODAK technical-data reversal profiles),
the interlayer DIR strength (runtime default, no `film_render_overrides`:
EKTACHROME 100D renders ColorChecker C* 35.9 against upstream's
`kodak_ektachrome_100` 37.5 and E100G 36.5, no clear mismatch; EIR is a
false-colour film, so a C* target does not apply), and for EIR the dropped
infrared response.

Without a No. 12 filter the infrared-sensitive (cyan-forming) layer's high
printed blue sensitivity dominates: blue subjects (sky) render magenta-red,
greens go dark blue-green, reds go green, and skin turns cyan-green (default
scanner, mid-grey a*b* about (8.6, -12.5)). This follows the printed curves;
it is not the familiar red-foliage infrared look, which needs infrared input.
