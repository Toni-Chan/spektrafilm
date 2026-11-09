# Per-stock film rendering overrides

One JSON file per film stock, `<stock>.json`, read by
`spektrafilm.runtime.params_builder.load_film_render_overrides` and applied in
`digest_params` (after the built-in stock specifics). The files are plain JSON
so downstream ports (e.g. SpektraLab) can read them without the Python runtime.

## Why these exist

Profiles built from data sheets (`*_fdg`, `kodak_*_<pubcode>`) get their
characteristic curves from **neutral, white-light exposures**. Those curves do
not encode interlayer interimage effects (DIR couplers in negatives, iodide
interimage in E-6 reversal films), which are the main design lever behind
"vivid"/"ultra"/"VS" stocks: the makers raise saturation *while keeping the
grey scale neutral* (Kodak E-163: "Color Amplifying Technology ... while
maintaining a neutral gray scale"). The runtime gives every film of a type the
same default DIR coupler matrix, so stocks whose saturation comes mainly from
interimage effects render too flat.

## Keys

| key | meaning |
| --- | --- |
| `dir_couplers_interlayer_scale` | multiplies the stock's interlayer DIR gammas (`gamma_interlayer_*`). Grey ramps are unchanged (the runtime pre-corrects the curves for the couplers). The user knob `dir_couplers.inhibition_interlayer` still multiplies on top. |
| `stock`, `estimate`, `note`, `calibration` | documentation only |

## Every value is an ESTIMATE

No data sheet publishes interimage strength. Each value is calibrated so the
stock lands where its maker ranks it, measured as mean CIE C*ab of the 18
colour patches of a synthetic ColorChecker 24 rendered with
`deactivate_stochastic_effects=True`, no auto exposure, negatives printed on
`kodak_portra_endura`, positives scanned. The calibration target and result
are recorded in each file. Positive films are capped at a scale of 1.8: above
about 2.0 the pre-correction of the curves starts to crush the blacks.
