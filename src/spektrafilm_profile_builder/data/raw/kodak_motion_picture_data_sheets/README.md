# KODAK motion picture camera negatives (EXR and VISION, 1993-2003) — raw curve records

Source: KODAK / Eastman Kodak motion picture technical data sheets (H-1-series, 1996-2003, and the
TI2082 technical-information sheet of 1993) as mirrored at <https://125px.com/docs/motionpicture/kodak/>
(each record's `info.txt` names the sheet, its publication code and date and the PDF URL; the PDFs are
not redistributed here). None of these sheets is catalogued by filmcolors.org. Page numbers are PDF pages.
The KODAK VISION3 stocks are not repeated here (they ship as hand-made profiles).

The curves are digitised with
[`scripts/extract_filmcolors_datasheets.py`](../../../../../scripts/extract_filmcolors_datasheets.py)
(`--raw` pointing at this folder), from the per-sheet configs `sheets/<publication>.json` (stock
metadata, caveats, builder recipe). The H-1 sheets carry their curves as vector art and are read straight
from the PDF paths (`{"path": [drawing, sub-path]}` seeds, no tracing); the EXR 500T sheet TI2082 prints
its curves as embedded ~137 dpi colour chart images (pages 7-9), traced colour by colour on the chart
grid. The overlay check images come from the script (`--checks`) and are not committed.

Exposure axes. The characteristic curves are read on the printed log H axis where its ticks are regular
(EXR 50D, 100T, 200T, 500T, VISION 500T 5263 / 5279). On the EXR 100T and VISION 500T 5263 sheets the
camera-stop axis drawn under the same plot disagrees with the log H axis by ~9-10% and is not used. The
VISION 250D and 320T sheets print hand-placed relative log-exposure ticks; their curves are read on the
regular camera-stop grid instead (1 stop = 0.30103 log H; both axes agree within ~1%). The absolute
exposure scale comes from the builder's speed-point anchoring in every case.

Dye densities. Most sheets print the mid-scale neutral and D-min densities; the 2002-2003 editions and the
1996 VISION 320T sheet also print peak-normalised C/M/Y dye curves, which the builder uses as the start of
its dye reconstruction. The VISION 250D dye plot's C/M/Y strokes are ambiguous (the yellow stroke runs on
into a red-region hump) and are not read. The VISION 500T 5279 sheet prints C/M/Y dye peaks only; its
mid-scale / D-min densities are borrowed from VISION 500T 5263 (`"borrow"`, listed in `info.txt`,
`extraction_summary.json` and the profile datasource as estimates) and it is built with a lower
`data_trustability`.

Not built: the March 1999 editions of EXR 50D 5245 (H-1-5245) and EXR 200T 5293 (H-1-5293) print the
same characteristic and sensitivity curves as their 2003 editions (identical to the drawing accuracy),
with fewer dye curves, and are superseded by them; the VISION 200T 5274 sheet (TI2325) on the mirror is
text only (its graphs pages are missing).

`records.csv` lists the records, `recipes.csv` is the batch recipe the profiles were built from (target
print KODAK VISION 2383; hanatos2025 adaptation parameters from pinned Kodak negative donors):

```bash
spektrafilm-profile-builder batch \
    src/spektrafilm_profile_builder/data/raw/kodak_motion_picture_data_sheets/recipes.csv \
    -o src/spektrafilm/data/profiles
```

| record / profile | sheet | date | art | notes |
|---|---|---|---|---|
| `kodak_exr_50d_5245` | EASTMAN EXR 50D 5245/7245, H-1-5245t, pp. 3-4 | 2003-05 | vector | daylight; C/M/Y dyes printed |
| `kodak_exr_100t_5248` | EASTMAN EXR 100T 5248/7248, H-1-7248, p. 3 | 1999-03 | vector | tungsten; log H axis (stop axis inconsistent) |
| `kodak_exr_200t_5293` | EASTMAN EXR 200T 5293/7293, H-1-5293t, pp. 3-4 | 2003-08 | vector | tungsten; C/M/Y dyes printed |
| `kodak_exr_500t_5298` | EASTMAN EXR 500T 5298/7298, TI2082, pp. 7-9 | 1993-10 | raster | tungsten; colour chart images |
| `kodak_vision_250d_5246` | KODAK VISION 250D 5246/7246, H-1-5246t, pp. 4-5 | 2003-03 | vector | daylight; camera-stop grid |
| `kodak_vision_320t_5277` | KODAK VISION 320T 5277/7277, H-1-5277t, p. 4 | 1996-03 | vector | tungsten; camera-stop grid; C/M/Y dyes printed |
| `kodak_vision_500t_5279` | KODAK VISION 500T 5279/7279, H-1-5279, pp. 2-3 | 1996-03 | vector | tungsten; mid/min dyes borrowed from 5263 |
| `kodak_vision_500t_5263` | KODAK VISION 500T 5263/7263, H-1-5263tx, pp. 3-4 | 2002-01 | vector | tungsten; log H axis (stop axis inconsistent) |
