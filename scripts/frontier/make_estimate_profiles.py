"""Regenerate the estimate-labelled Frontier capture/render profiles.

Run from the repo root:  python scripts/frontier/make_estimate_profiles.py
Every value written here is a placeholder (label ``estimate`` or
``community``); replace with lab data per docs/frontier/evidence.md.
"""
from __future__ import annotations

import json
from pathlib import Path

import colour
import numpy as np

OUT = Path(__file__).resolve().parents[2] / "src" / "spektrafilm" / "data" / "scanners"

PRESETS = {
    # name: (B, G, R) peaks nm, source
    "community_a": ((460.0, 550.0, 630.0), "R9 Negative Lab Pro forum"),
    "community_b": ((475.0, 525.0, 630.0), "R10 Negative Lab Pro forum"),
    "community_c": ((465.0, 550.0, 630.0), "R14 photo.net (B,R); G taken from community_a"),
}
FWHM = {"B": 20.0, "G": 30.0, "R": 20.0}

# Tabulated LED spectra digitised from the SP3000 light-source plot posted on
# discuss.pixls.us (R17). Each LED is normalised to its own peak; the plot gives
# no relative power between LEDs. Treated as identical for the SP500.
SPD_FIT = Path(__file__).resolve().parent / "data" / "sp3000_led_fit.json"
SPD_PRESET = "community_spd"

QE_NODES = [380, 420, 460, 500, 550, 600, 650, 700, 780]
QE_REL = [0.20, 0.38, 0.55, 0.72, 0.90, 1.00, 0.95, 0.82, 0.55]

MODELS = {
    "frontier_sp500": "Frontier SP500: LED illumination, area CCD (R1).",
    "frontier_sp3000": "Frontier SP3000: LED board R64/G40/B50/IR144, Super CCD Honeycomb area sensor (R2 PDF p.13, p.46).",
}


def prov(label, source, locator="", notes=""):
    return {"label": label, "source": source, "locator": locator, "notes": notes}


def _leds_from_spd():
    fit = json.loads(SPD_FIT.read_text())
    leds = {}
    for ch in ("R", "G", "B"):
        f = fit["fit"][ch]
        leds[ch] = {
            "wavelengths_nm": fit["wavelengths"],
            "values": fit["tables"][ch],
            "provenance": prov(
                "community", "R17", "discuss.pixls.us t/20271 post 13, 'Fuji Frontier SP3000' spectrum",
                notes=(f"digitised plot, split pseudo-Voigt fit; peak {f['peak_nm']} nm, FWHM {f['fwhm_nm']} nm, "
                       f"fit RMS {f['fit_rms']}; SP500 assumed identical; replace via FRT-15"),
            ),
        }
    return leds


def capture(model, preset):
    if preset == SPD_PRESET:
        leds = _leds_from_spd()
    else:
        peaks, src = PRESETS[preset]
        b, g, r = peaks
        leds = {}
        for ch, pk in (("R", r), ("G", g), ("B", b)):
            leds[ch] = {
                "gaussian": {"peak_nm": pk, "fwhm_nm": FWHM[ch], "skew": 0.0},
                "provenance": prov("community", src, notes=f"FWHM {FWHM[ch]} nm is an estimate from LED datasheets R15/R16; replace via FRT-15"),
            }
    return {
        "id": f"{model}_{preset}",
        "description": MODELS[model] + " Placeholder capture profile; spectral values are not measured.",
        "led_spd": leds,
        "filters": [],
        "sensor_qe": {
            "wavelengths_nm": QE_NODES, "values": QE_REL,
            "provenance": prov("estimate", "generic front-illuminated silicon CCD shape; R8 comparator only", notes="replace via FRT-14"),
        },
        "effective_kernels": None,
        "mtf": {
            "gaussians_um": [],
            "flare": {"fraction": 0.0, "sigma_um": 500.0},
            "provenance": prov("estimate", "no data; ideal optics until slanted-edge/flare measurement", notes="replace via FRT-16/FRT-24"),
        },
        "pixel_shift": {"active": False, "provenance": prov("official", "R2", "PDF p.46", "pixel shifting exists; not simulated yet")},
        "noise": {"full_well_e": None, "read_noise_e": 0.0, "provenance": prov("estimate", "no data; noise off until flat-field measurement", notes="replace via FRT-13")},
        "adc_bits": {"value": 12, "provenance": prov("estimate", "no public spec", notes="replace via FRT-13")},
        "provenance": prov("estimate", "docs/frontier/evidence.md default template"),
    }


def render():
    m = colour.RGB_COLOURSPACES["sRGB"].matrix_RGB_to_XYZ
    return {
        "id": "frontier_estimate",
        "description": "Placeholder Frontier positive rendering. Gradation, balance and matrix are estimates.",
        "gradation": {
            "type": "log_linear_rolloff",
            "contrast_slopes": {"soft": 0.85, "standard": 1.0, "hard": 1.15},
            "midgray_out": 0.18,
            "white_rolloff": 6.0,
            "provenance": prov("estimate", "no published Frontier gradation", notes="replace via FRT-13/FRT-23"),
        },
        "balance": {
            "method": "stock_midgray",
            "provenance": prov("estimate", "Frontier per-film-type channel setup assumed to neutralise stock mid-grey", notes="replace via FRT-17"),
        },
        "matrix_instrument_to_xyz": {
            "value": np.asarray(m).round(10).tolist(),
            "provenance": prov("estimate", "sRGB primaries (IEC 61966-2-1) used as placeholder", notes="refit via scripts/frontier/fit_placeholder_matrix.py or FRT-24"),
        },
        "provenance": prov("estimate", "docs/frontier/evidence.md default template"),
    }


def main():
    for model in MODELS:
        for preset in (*PRESETS, SPD_PRESET):
            d = capture(model, preset)
            (OUT / "capture" / f"{d['id']}.json").write_text(json.dumps(d, indent=2) + "\n")
    d = render()
    (OUT / "render" / f"{d['id']}.json").write_text(json.dumps(d, indent=2) + "\n")


if __name__ == "__main__":
    main()
