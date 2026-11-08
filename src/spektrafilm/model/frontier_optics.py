"""Frontier scanner optics and sensor effects on instrument RGB.

All parameters come from the capture profile (``mtf``, ``noise``, ``adc_bits``)
and are ``estimate``-labelled until slanted-edge and flat-field data exist (FRT-24).
"""
from __future__ import annotations

import numpy as np

from spektrafilm.model.diffusion import apply_gaussian_blur

CHANNELS = ("R", "G", "B")


def _gaussians_for_channel(spec: dict, c: str) -> list:
    g = spec.get("gaussians_um", [])
    if isinstance(g, dict):
        g = g.get(c, [])
    return [(float(s), float(w)) for s, w in g]


def mtf_curve(spec: dict, freq_cyc_per_um: np.ndarray, channel: str = "G") -> np.ndarray:
    """Analytic MTF of a sum-of-Gaussians PSF; weights are normalised to 1."""
    gs = _gaussians_for_channel(spec, channel)
    if not gs:
        return np.ones_like(np.asarray(freq_cyc_per_um, dtype=np.float64))
    wsum = sum(w for _, w in gs)
    f = np.asarray(freq_cyc_per_um, dtype=np.float64)
    return sum(w / wsum * np.exp(-2.0 * np.pi**2 * s**2 * f**2) for s, w in gs)


def apply_mtf(rgb: np.ndarray, mtf_spec: dict, pixel_size_um: float | None) -> np.ndarray:
    """Blur each channel with its sum-of-Gaussians PSF (sigmas in micrometres on the film)."""
    if not mtf_spec or not any(_gaussians_for_channel(mtf_spec, c) for c in CHANNELS):
        return rgb
    if not pixel_size_um:
        raise ValueError("apply_mtf needs pixel_size_um")
    out = np.empty_like(rgb, dtype=np.float64)
    for i, c in enumerate(CHANNELS):
        gs = _gaussians_for_channel(mtf_spec, c)
        ch = np.ascontiguousarray(rgb[..., i:i + 1], dtype=np.float64)
        if not gs:
            out[..., i] = ch[..., 0]
            continue
        wsum = sum(w for _, w in gs)
        acc = np.zeros_like(ch)
        for s_um, w in gs:
            acc += (w / wsum) * apply_gaussian_blur(ch, s_um / pixel_size_um)
        out[..., i] = acc[..., 0]
    return out


def apply_flare(rgb: np.ndarray, spec: dict | None, pixel_size_um: float | None) -> np.ndarray:
    """Diffuser/lens veiling flare: a fraction of light redistributed by a wide Gaussian."""
    if not spec:
        return rgb
    frac = float(spec.get("fraction", 0.0))
    if frac <= 0:
        return rgb
    if not pixel_size_um:
        raise ValueError("apply_flare needs pixel_size_um")
    sigma = float(spec["sigma_um"]) / pixel_size_um
    wide = apply_gaussian_blur(np.ascontiguousarray(rgb, dtype=np.float64), sigma)
    return (1.0 - frac) * rgb + frac * wide


def add_sensor_noise(s: np.ndarray, noise: dict | None, rng: np.random.Generator) -> np.ndarray:
    """Shot + read noise. ``s`` is signal relative to full well (1.0 = full well).

    ``full_well_e`` None disables shot noise; ``read_noise_e`` is in electrons
    (needs ``full_well_e``).
    """
    if not noise:
        return s
    fw = noise.get("full_well_e")
    rn = float(noise.get("read_noise_e", 0.0) or 0.0)
    if not fw:
        return s
    fw = float(fw)
    var_e = np.fmax(s, 0.0) * fw + rn**2
    if not np.any(var_e > 0):
        return s
    return s + rng.standard_normal(s.shape) * np.sqrt(var_e) / fw


def quantise(s: np.ndarray, bits: int | None) -> np.ndarray:
    """Uniform ADC quantisation of [0, 1] signal; ``bits`` None = no quantisation."""
    if bits is None:
        return s
    levels = float(2**int(bits) - 1)
    return np.round(np.clip(s, 0.0, 1.0) * levels) / levels
