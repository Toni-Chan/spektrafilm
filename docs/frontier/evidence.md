# Frontier SP500 / SP3000 evidence register

Every number used by the Frontier scanning simulation must appear here with a
provenance label, a source and a locator.

Labels: **official** (Fujifilm document + page), **patent** (number + column),
**community** (URL; conflicting claims kept side by side), **estimate**
(rationale + lab ticket that will replace it), **measured** (dataset id).

Source keys refer to `references.bib` (R1–R28 in the development plan).

## Hardware facts

| # | Fact | Value | Label | Source | Locator |
|---|------|-------|-------|--------|---------|
| H1 | SP3000 light source | High-luminance LED type, diffusion box | official | R2 | SP3000 operator manual, specifications (PDF p.46) |
| H2 | SP3000 sensor | Super CCD Honeycomb, area type, precision pixel shifting | official | R2 | SP3000 operator manual, specifications (PDF p.46) |
| H3 | SP3000 LED board counts | R×64, G×40, B×50, IR×144 | official | R2 | SP3000 operator manual, "LED Light Source Unit" (PDF p.13) |
| H4 | SP3000 sensor colour | Black-and-white area CCD (colour via sequential LED exposure) | official | R2 | PDF p.13 |
| H5 | IR-cut and R-cut filters in optical path | present | unverified | R3 | Service manual FR355375; not found in R2, needs page check |
| H6 | SP500 light source / sensor | LED + area CCD | official | R1 | SP500 specifications page |

## LED peak wavelengths (no official value found)

| # | Claim (B / G / R nm) | Label | Source |
|---|----------------------|-------|--------|
| L1 | 460 / 550 / 630 | community | R9 |
| L2 | 475 / 525 / 630 | community | R10 |
| L3 | 465 (B) / 630 (R) | community | R14 |
| L4 | FWHM 20–30 nm typical for InGaN/AlInGaP colour LEDs | official (LED vendor, generic) | R15, R16 |
| L5 | SP3000 light-source spectrum plot: peaks 463.5 / 536.6 / 630.2 nm, FWHM 21.5 / 37.1 / 17.1 nm, Lorentzian-like tails; each LED normalised to its own peak, so no relative power | community (digitised plot, origin of measurement not stated) | R17 |

L5 is the basis of the `community_spd` capture preset, which is now the default for both `frontier_sp3000` and `frontier_sp500` (the SP500 is assumed to use the same LEDs). Digitised data and fit: `scripts/frontier/data/sp3000_led_envelope_pixls.csv`, `scripts/frontier/data/sp3000_led_fit.json`. The plot's region above 670 nm is hidden by its title, so the red long-wavelength tail beyond that is extrapolated by the fit.

## Sensor linearity

| # | Claim | Label | Source |
|---|-------|-------|--------|
| S1 | CCDs are essentially linear until the charge wells fill, then stop responding (hard clip) | community (trade press, 2003) | R18 |
| S2 | Fuji's 4th-gen Super CCD *SR* adds low-sensitivity R-pixels for ~4x highlight range, giving a non-linear combined response | official (Fujifilm press release quoted in R18) | R18 |

The capture model assumes S1. S2 applies to SR-type sensors only; the SP3000 is documented as a Super CCD Honeycomb area sensor (R2), with no evidence of SR dual pixels, so no SR response is modelled.

## Default template values (all `estimate`)

These live in `src/spektrafilm/data/scanners/frontier_default.json`.

| Parameter | Default | Rationale | Replaced by |
|-----------|---------|-----------|-------------|
| LED spectra B/G/R | tabulated from L5 (peaks 463.5 / 536.6 / 630.2 nm) | `community_spd` preset, default | FRT-15 |
| LED peaks/FWHM (older presets) | 460 / 550 / 630 nm, 20 / 30 / 20 nm | L1 + R15/R16, kept as `community_a/b/c` | FRT-15 |
| CCD relative QE | generic silicon front-illuminated curve | R8 comparator only | FRT-14 |
| Tone response | linear, 12-bit, black offset 0, hard clip at full scale | CCDs respond linearly up to well saturation (R18, general CCD behaviour, not a Frontier measurement) | FRT-13 |
| Sharpening | off | user setting dependent | FRT-16 |
| Hyper Tone | 0 | user setting dependent | FRT-16 |

## Unknowns → lab tickets

| Unknown | Ticket |
|---------|--------|
| Scanner tone/OECF from step wedge | FRT-13 |
| Effective channel spectral sensitivity | FRT-14 |
| LED peak/FWHM validation | FRT-15 |
| Sharpening and Hyper Tone kernels | FRT-16 |
| Auto setup behaviour on a known roll | FRT-17 |
