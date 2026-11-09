# spektrafilm_profile_builder — film profiles from data-sheet curves

Builds spektrafilm film profiles (the JSON files in
`src/spektrafilm/data/profiles`) from digitised manufacturer data-sheet
curves, and ships the 25 colour profiles made from the **Fujifilm
Professional Data Guide** (`*_fdg`).

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

# 4th-colour-layer sidecars for the built negatives that have the curve
spektrafilm-profile-builder extensions \
    src/spektrafilm_profile_builder/data/raw/fujifilm_professional_data_guide/recipes.csv \
    --profiles src/spektrafilm/data/profiles -o src/spektrafilm/data/profile_extensions

# neutral enlarger filters for existing profile JSONs (merged into the JSON file)
spektrafilm-profile-builder fit-filters out/my_film.json --filters-json out/neutral_print_filters.json

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
| `info.txt` | first line = stock name, `Key: value` lines are read (e.g. `Type: positive`) | |

Anything else in the folder (MTF, Fuji's 4th "cyan-sensitive" layer...) is
kept for reference and ignored.

Fuji's 4th colour layer (`log_sensitivity_cyan_layer.csv`, the cyan-sensitive
inhibitor layer of REALA / PRO / X-TRA / nexia negatives) is **not** folded
into the red `log_sensitivity` and is **not** written into the profile JSON
(upstream's loader builds `ProfileData(**data)` and rejects unknown keys).
The `extensions` command turns it into a profile-extension sidecar instead;
see [Fuji's 4th colour layer](#fujis-4th-colour-layer-cyan-inhibitor) below.

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

## Fuji's 4th colour layer (cyan inhibitor)

### Physics

Fujifilm REALA-generation negatives (Superia REALA, PRO 160S/160C/400H/800Z,
Superia 100-1600, X-TRA, nexia, NPL) have a fourth colour-sensitive layer.
It is sensitive to blue-green light (the Pro Data Guide prints its curve next
to R, G and B; it peaks at 515-525 nm) but forms **no image dye**. When it
develops it releases DIR (development-inhibitor-releasing) compounds into the
red-sensitive layer, so blue-green light *lowers* the red record. In effect
the red channel acquires a negative spectral response around 500-520 nm,
which is the negative lobe of the CIE 1931 r-bar colour-matching function
(minimum at 515 nm); Fujifilm presented it as bringing film's colour response
closer to human vision (cleaner greens and blue-greens, better behaviour
under fluorescent light).

### Model

The runtime (`spektrafilm.model.couplers.InhibitorExposure`, used by
`develop()` inside the DIR-coupler stage) treats the layer as an extra
inhibitor donor:

1. **Exposure.** A 4th raw exposure is computed from the layer's spectral
   sensitivity with exactly the same spectral integration as R, G, B (the
   hanatos2025 or mallett2019 upsampling, the profile's hanatos2025 spectral
   window and any camera UV/IR filter; not the per-channel exposure-correction
   surface, which is fitted for R, G, B only). It is normalised so that
   18.4 % grey gives the same raw exposure as the green layer. Exposure-side
   operations (exposure compensation, highlight boost, lens blur, camera
   diffusion filter, halation) are carried over with the green layer's
   per-pixel gain; exposure scalings are exact, spatial ones are approximated
   by green's (the layer sits next to the green layer). LUT mode has no
   spatial effects, so it is exact there.
2. **Silver.** The layer's developed silver follows the normalised
   characteristic-curve shape of the red layer (the sheet publishes no curve
   for a layer without dye; red is the layer it acts on, and using the same
   shape means a neutral exposure gives identical silver).
3. **Inhibition, departure from neutral.** The data-sheet curves are measured
   with neutral light, i.e. *with* the 4th layer already inhibiting red at its
   neutral level. So only the departure from neutral is applied:

   `delta log E_red = -amount * [D(log E_cyan) - D(log E_green)]`

   `E_green` is the neutral-equivalent reference: for any neutral exposure
   `E_cyan == E_green`, so grey ramps are reproduced *exactly* (dE00 = 0.000
   on a -3..+3 EV ramp, LUT mode and spatial mode) and the density curves need
   no re-derivation. The term is diffused with the same Gaussian + exponential
   kernel as the DIR couplers and subtracted from the red log exposure before
   the DIR-coupler correction.

   *Why green and not red as the reference.* Using the red exposure as the
   reference (`D(log E_cyan) - D(log E_red)`) is the other neutral-preserving
   choice. It makes the layer a second, strong red-saturation coupler: every
   colour with little blue-green content (reds, skin, oranges) gets up to
   `amount * D_red` more red exposure (in a trial with a comparable lobe
   depth, up to 13 dE00 on the ColorChecker skin and red patches), which duplicates what the generic G->R DIR coupler already models
   and is not what the layer is for. The cyan layer's band lies inside the
   green band, so the green exposure is what the layer "would have received"
   for a spectrally flat colour of the same brightness. The difference that
   remains is the *spectral* information the 4th layer adds: blue-green-rich
   light (E_cyan > E_green) removes red, yellow-green-rich light
   (E_cyan < E_green) adds it.
4. **Strength.** `amount` comes from the sidecar (`amount_default`) times
   `DirCouplersParams.cyan_inhibitor_scale` times the global DIR `amount`;
   `cyan_inhibitor_active` switches it off. Both are in the GUI's *Couplers*
   panel. With DIR couplers off the layer is off too.

### Default amount (an estimate)

The data sheet gives the layer's spectral sensitivity, not how strongly it
inhibits, so `amount_default` is an **estimate**, labelled `"label": "estimate"`
in every sidecar with its derivation in `amount_basis`. It is calibrated per
stock so that the effective red spectral sensitivity of the *full film model*
(narrowband sweep on mid-grey through `develop()`, default negative
DIR-coupler matrix) has a negative lobe at 500-530 nm as deep, relative to its
positive peak, as CIE r-bar's: 0.0936 / 0.3476 = 0.269. The generic DIR
couplers alone already give a shallower dip there (ratio -0.04 to -0.12,
recorded as `effective_red_lobe_ratio_without_layer`). Resulting values: 0.23
(NPL 160) to 1.01 (Superia REALA); PRO 400H 0.95.

Validation (PRO 400H and Superia REALA on Crystal Archive Type II):
ColorChecker mean dE00 on vs off 0.86 / 0.66, max 2.1 / 2.6 (yellow-green,
foliage, blue flower, green; yellow-greens and skin get slightly warmer,
blue-greens and blues slightly less red); neutral patches <= 0.09 (the 0.09 is
the white patch, which is not exactly neutral); grey ramp 0.000.

### Sidecar format

`src/spektrafilm/data/profile_extensions/<stock>.json`, read by
`spektrafilm.profiles.extensions.load_profile_extension()`:

```json
{
  "stock": "fujifilm_pro_400h_fdg",
  "version": 1,
  "inhibitor_layers": [
    {
      "name": "cyan",
      "target": "r",
      "reference": "g",
      "amount_default": 0.9548,
      "label": "estimate",
      "source": "Fujifilm Professional Data Guide ... page 30 ...",
      "notes": "...",
      "amount_basis": "...",
      "wavelengths": [380.0, 385.0, "... 81 values, the profile grid ..."],
      "log_sensitivity": ["... 81 values, log10, 18.4 % grey -> raw 1 ..."]
    }
  ]
}
```

Extra keys (`gamma_r_at_midgray`, `printed_range_nm`,
`printed_peak_log_sensitivity_relative_to_red_peak`, ...) are provenance
only. No sidecar = feature off; a profile without one (all non-Fuji
profiles) renders bit-identically to a build without this code.

### Downstream forks

* The profile JSONs are unchanged, so upstream spektrafilm, SpektraLab and
  other readers keep loading them; they simply ignore the 4th layer.
* SpektraLab's `bake_resources.py` copies only `data/profiles/*.json`, and its
  `gen_catalog.py` treats every file there as a stock, which is why the
  sidecars live in a separate directory. To *use* the layer, SpektraLab's C++
  engine needs its own port: compute the 4th raw exposure with the sidecar
  sensitivity (same upsampling, normalised to green at mid-grey), look up
  `D` on the red density curve for it and for the green exposure, and
  subtract `amount * (D_cyan - D_green)` (diffused like the DIR couplers) from
  the red log exposure before the coupler correction.
* Python forks of spektrafilm can copy `profiles/extensions.py`, the
  `profile_extensions/` directory and the `InhibitorExposure` changes in
  `model/couplers.py`, `model/develop.py` and `runtime/stages/filming.py`.
* LUT bakes: 1-LUT and 2-LUT bundles include the effect. 3-LUT and 4-LUT
  bundles split the chain at `log_e_film`, which carries no 4th-layer
  exposure, so their filming-develop cube is baked without it (the builder
  warns). Injecting a pipeline at the `log_e_film` tap likewise renders with
  the layer off.

## Licence and provenance

Code: GPLv3, like the rest of the repository. Profiles: CC BY-SA 4.0 with
the spektrafilm profile attribution (see `SPEKTRAFILM_LICENSE.txt`); the
`metadata.datasource` of each profile names the source page. The raw curves
are digitised from the Fujifilm Professional Data Guide AF3-207U (2005),
publicly published by FUJIFILM Corporation; the data remain property of
their holder. See
[data/raw/fujifilm_professional_data_guide/README.md](data/raw/fujifilm_professional_data_guide/README.md).
