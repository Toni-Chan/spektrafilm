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

## Default template values (all `estimate`)

These live in `src/spektrafilm/data/scanners/frontier_default.json`.

| Parameter | Default | Rationale | Replaced by |
|-----------|---------|-----------|-------------|
| LED peaks B/G/R | 460 / 550 / 630 nm | L1, midpoint of community claims | FRT-15 |
| LED FWHM B/G/R | 25 / 30 / 20 nm | R15/R16 typical | FRT-15 |
| CCD relative QE | generic silicon front-illuminated curve | R8 comparator only | FRT-14 |
| Tone response | linear, 12-bit, black offset 0 | no data | FRT-13 |
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
