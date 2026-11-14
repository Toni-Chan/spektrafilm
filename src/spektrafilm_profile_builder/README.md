# spektrafilm_profile_builder — film profiles from data-sheet curves

Builds spektrafilm film profiles (the JSON files in
`src/spektrafilm/data/profiles`) from digitised manufacturer data-sheet
curves, and ships the 25 colour profiles made from the **Fujifilm
Professional Data Guide** (`*_fdg`) and the 66 film and print-material
profiles made from the **KODAK technical data sheets** (E-series, 1997-2003,
and E-55 KODACHROME, 2009; `kodak_<stock>_<pubcode>`, e.g.
`kodak_portra_160nc_e190`, `kodak_kodachrome_25_e55`).

It is the historical upstream raw-curve factory (`profiles_factory`, last
public at commit `049f677^`) restored, ported to the current module layout and
profile schema, and turned into a reusable command-line tool. Like the GUI and
the LUT creator it sits *above* the runtime core: it imports `spektrafilm`,
the runtime never imports it, and it writes nothing but standard profile
fields, so the output works in any program that reads spektrafilm profiles.

## Command line

```bash
# one record folder -> one profile
spektrafilm-profile-builder build path/to/record --stock my_film --name "My Film 400" \
    --type negative --target-print kodak_portra_endura -o out/ [--filters-json out/neutral_print_filters.json]

# every row of a recipe CSV (this is how the *_fdg profiles were built)
spektrafilm-profile-builder batch \
    src/spektrafilm_profile_builder/data/raw/fujifilm_professional_data_guide/recipes.csv \
    -o src/spektrafilm/data/profiles \
    --filters-json src/spektrafilm/data/filters/neutral_print_filters.json

# a print paper / print material (stage 'printing'); --support film for a backlit display transparency
spektrafilm-profile-builder build path/to/paper_record --stock my_paper --name "My Paper" \
    --type paper --reference-illuminant TH-KG3 -o out/

# neutral enlarger filters for existing profile JSONs or shipped ids (merged into the JSON file);
# --papers limits the papers, --only-missing never overwrites an existing entry
spektrafilm-profile-builder fit-filters out/my_film.json kodak_portra_400 --filters-json out/neutral_print_filters.json \
    [--papers my_paper,kodak_portra_endura] [--only-missing]

# catalogue rows (name, short name, ISO, swatch...) for apps that keep their own stock list
spektrafilm-profile-builder catalog out/*.json
```

`python -m spektrafilm_profile_builder ...` is equivalent (use it when the
package is on `PYTHONPATH` but not installed). Building one negative takes
about a minute (the grey-ramp refinement runs the full pipeline); add
`--no-grey-ramp` for a quick draft.

## Record layout

A record is a folder of headerless `x, y` CSV files, the layout the upstream
raw data used:

| file | x | y |
|---|---|---|
| `log_sensitivity_{r,g,b}.csv` | wavelength (nm) | log10 spectral sensitivity |
| `density_curve_{r,g,b}.csv` | log10 exposure (lux s) | total density (base+fog included) |
| `dye_density_{c,m,y}.csv` | wavelength (nm) | spectral dye density (reversal films) |
| `dye_density_{mid,min}.csv` | wavelength (nm) | mid-scale neutral / minimum density (colour negatives) |
| `info.txt` | first line = stock name, `Key: value` lines are read (e.g. `Type: positive`, `Type: paper`) | |

Anything else in the folder (MTF, Fuji's 4th "cyan-sensitive" layer...) is
kept for reference and ignored.

Fuji's 4th colour layer (`log_sensitivity_cyan_layer.csv`, the cyan-sensitive
inhibitor layer of REALA / PRO / X-TRA negatives) is deliberately **not**
folded into the red `log_sensitivity`: the red channel is built from
`log_sensitivity_r.csv` alone. The curve is not written into the profile JSON
either, because upstream's loader builds `ProfileData(**data)` and rejects
unknown keys (a profile with an extra `data` key fails to load with
`TypeError`). Modelling the layer (e.g. as an extra inhibitor term in the DIR
coupler stage) needs a schema + runtime change and is left for a separate PR;
the raw curve stays in the record for that.

## Processing

Negative (status M):

1. sensitivity tails outside the printed range are continued smoothly (the
   runtime needs finite values on 380-780 nm);
2. base+fog is removed from the curves (toe fit) and log exposure 0 is put at
   mid-grey: green 0.2 over D-min plus 3 stops (upstream convention);
3. C, M, Y dye densities are reconstructed from the mid-scale neutral and
   minimum spectral densities (`reconstruct.py`, the upstream `dmid_dmin`
   model starting from the bundled `generic_a` dyes, ported from lmfit to
   scipy);
4. dyes are normalised to unit status density and the status-M curves are
   unmixed into per-layer densities with the densitometer crosstalk matrix;
5. the curves are fitted with the three-layer normal-CDF (`cdfs`) model;
6. sensitivities are scaled so that 18.4 % grey under the reference
   illuminant gives raw exposure 1 per channel (what the runtime's hanatos2025
   upsampling expects). Data-sheet curves are white-light curves, so no
   per-channel curve shift is needed and the printed sensitivity zero point —
   only relative on Fuji negative sheets, which print a 1.0 bracket but no
   axis numbers — drops out;
7. grey-ramp refinement through the runtime (upstream
   `correct_negative_curves_with_gray_ramp`): an EV -2..+6 ramp of mid-grey is
   printed on the target paper, and per-channel density scales plus R/B
   log-exposure shifts are fitted so it prints neutral, with a penalty
   weighted by `data_trustability` (0.3, the value upstream used for Fuji);
8. neutral Y/M enlarger filters are fitted for every shipped paper
   (TH-KG3 enlarger lamp) and merged into `neutral_print_filters.json`.

Positive / reversal (status A): the sheet's C, M, Y dye densities are used
directly (peak-normalised, then normalised to unit status density). A dye
printed over a shorter range than the others is continued with an
exponential decay over the range any dye covers: the runtime treats NaN
spectral density as opaque, so e.g. Velvia 50's yellow dye (printed only to
600 nm) would otherwise black out the red end of the spectrum. Base+fog is
spread spectrally from the status-A minima; mid-grey starts at green D =
0.735 over D-min (old upstream factory convention); steps 4-7 as above, with
the ramp (EV -1..+2) scanned directly and only its colour balance fitted.
Finally a common log-exposure shift makes the scanned mid-grey render at
18.4 % at 0 EV, which is what all shipped reversal profiles do (net density
about 0.5 at log exposure 0). The mid-scale neutral density is
`channel_density @ D(0) + base_density`.

Two opt-in recipe fields (CLI `--density-min`, `--dye-extension`) cover sheets
whose curves stop short; both are estimate placeholders and the KODAK recipe
writes them into the profile's `metadata.datasource`:

* `density_min` (`r;g;b` status densities): base+fog used instead of the toe
  fit, for characteristic curves that end before reaching D-min (the fit then
  extrapolates, possibly below zero);
* `dye_extension: hold_decay` (positives): dyes are continued outside the
  printed range too (first printed value held towards 380 nm, exponential
  decay from the last one towards 780 nm), instead of staying NaN (opaque).

Paper / print material (`--type paper`, status A), following upstream's
`process_paper_profile`: base+fog is removed and spread spectrally from the
status-A minima; log exposure 0 is put where green reaches D = 0.735 over
D-min; the dyes (peak-normalised on 420-700 nm, since paper sheets draw every
dye rising into the UV) are scaled so that their mixture plus base is a
metameric 18.4 % neutral under the viewing illuminant (amounts relative to
green); the status-A curves are unmixed and fitted with the `cdfs` model. The
spectral sensitivities are kept as printed (their R/G/B balance sets the
enlarger filtration; the absolute level cancels in the runtime's print
exposure normalisation), with the tails continued. The profile is written with
`type: negative`, `stage: printing`, `support: paper` (or `film` for backlit
display transparencies, like `kodak_2383`), reference illuminant `TH-KG3`, and
no hanatos2025 parameters, as the shipped papers.

The hanatos2025 adaptation parameters (spectral window, exposure-correction
surface) are fitted by upstream's private profile creator and are not
constrained by a data sheet; the builder averages those of shipped profiles
of the same maker and type (`--adaptation-donors` to choose).

## Using the profiles in a fork

The profiles use only fields that exist upstream, so any program that reads
spektrafilm profiles can load them:

* **spektrafilm forks**: copy the `*_fdg.json` files into
  `src/spektrafilm/data/profiles/`, merge the `*_fdg` entries of
  `src/spektrafilm/data/filters/neutral_print_filters.json`, and (to see them
  in the GUI picker) add them to `FilmStocks` in
  `src/spektrafilm/model/stocks.py`.
* **SpektraLab (macOS)**: `engine/tools/bake_resources.py` copies every
  `*.json` from the installed spektrafilm's `data/profiles` and its
  `neutral_print_filters.json`, so with this branch installed in the Python
  environment SpektraLab bakes from, rerun `bake_resources.py`. Its
  `app/SpektraLab/tools/gen_catalog.py` refuses profiles it has no name for:
  `spektrafilm-profile-builder catalog src/spektrafilm/data/profiles/*_fdg.json`
  prints the rows (name, short name, kind, ISO, swatch) to add to its
  `NAMES`, `ORDER` and `CHOSEN` tables, then rerun `gen_catalog.py` and
  rebuild the app.
* **Other ports**: the JSON schema is the one in
  `src/spektrafilm/profiles/io.py`; `density_curves_model` (cdfs, 3 layers)
  and `density_curves_layers` are filled, sensitivities are finite, densities
  are `null` outside the printed wavelength range like the shipped profiles.

## Licence and provenance

Code: GPLv3, like the rest of the repository. Profiles: CC BY-SA 4.0 with
the spektrafilm profile attribution (see `SPEKTRAFILM_LICENSE.txt`); the
`metadata.datasource` of each profile names the source page. The raw curves
are digitised from the Fujifilm Professional Data Guide AF3-207U (2005),
publicly published by FUJIFILM Corporation, and from the KODAK technical data
sheets (E-series) published by Eastman Kodak Company, and from data sheets
catalogued by filmcolors.org (Timeline of Historical Film Colors); the data
remain property of their holders and the source PDFs are not redistributed. See
[data/raw/fujifilm_professional_data_guide/README.md](data/raw/fujifilm_professional_data_guide/README.md),
[data/raw/kodak_technical_data/README.md](data/raw/kodak_technical_data/README.md)
and [data/raw/filmcolors_data_sheets/README.md](data/raw/filmcolors_data_sheets/README.md).
