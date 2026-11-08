"""Surrogates for Frontier Hyper Tone and sharpness (estimates until FRT-24).

Hyper Tone is modelled as edge-aware compression of large-scale luminance
contrast (a guided filter on the rendered log luminance); sharpness as a
single unsharp mask on the rendered linear image. Neither is a reverse
engineering of Fujifilm's algorithms.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import uniform_filter

from spektrafilm.model.diffusion import apply_unsharp_mask

# (sigma_px, amount) per level, label: estimate (HARMAN R4 recommends low
# Frontier sharpness for film; magnitudes are guesses to be replaced via FRT-24)
SHARPNESS_PRESETS = {"off": (0.0, 0.0), "low": (1.0, 0.3), "std": (1.0, 0.6), "high": (1.2, 1.0)}
HYPER_TONE_RADIUS_FRACTION = 0.05  # estimate: fraction of the longer image side
HYPER_TONE_EPS = 0.01              # estimate: guided-filter edge threshold (log10 units squared)


def _guided_filter(guide: np.ndarray, src: np.ndarray, radius: int, eps: float) -> np.ndarray:
    size = 2 * radius + 1
    mean_i = uniform_filter(guide, size, mode="reflect")
    mean_p = uniform_filter(src, size, mode="reflect")
    corr_ip = uniform_filter(guide * src, size, mode="reflect")
    var_i = uniform_filter(guide * guide, size, mode="reflect") - mean_i**2
    a = (corr_ip - mean_i * mean_p) / (var_i + eps)
    b = mean_p - a * mean_i
    return uniform_filter(a, size, mode="reflect") * guide + uniform_filter(b, size, mode="reflect")


def hyper_tone(log_exposure: np.ndarray, strength: float) -> np.ndarray:
    """Compress large-scale luminance in the rendered log domain, keep local detail.

    ``log_exposure``: (H, W, 3) log10 relative exposure (mid-grey = 0).
    ``strength`` in [0, 1]: 0 = no change, 1 = flatten the large-scale base fully.
    """
    if strength == 0.0:
        return log_exposure
    if not 0.0 < strength <= 1.0:
        raise ValueError("hyper_tone strength must be in [0, 1]")
    lum = log_exposure.mean(axis=-1)
    radius = max(1, int(round(HYPER_TONE_RADIUS_FRACTION * max(lum.shape))))
    base = _guided_filter(lum, lum, radius, HYPER_TONE_EPS)
    return log_exposure - strength * base[..., None]


def frontier_sharpen(rgb: np.ndarray, level: str) -> np.ndarray:
    if level not in SHARPNESS_PRESETS:
        raise ValueError(f"unknown sharpness {level!r}; expected one of {list(SHARPNESS_PRESETS)}")
    sigma, amount = SHARPNESS_PRESETS[level]
    if amount == 0.0:
        return rgb
    return np.clip(apply_unsharp_mask(np.ascontiguousarray(rgb, dtype=np.float64), sigma=sigma, amount=amount),
                   0.0, None)
