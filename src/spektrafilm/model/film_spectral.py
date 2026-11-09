"""Spectral density of a developed film from its CMY dye densities.

Thin, shape-agnostic wrapper around :func:`spektrafilm.model.develop.compute_density_spectral`,
which is what ``ScanningStage`` uses; the result is identical for (H, W, 3) input.
"""
from __future__ import annotations

import numpy as np

from spektrafilm.model.develop import compute_density_spectral


def film_spectral_density(cmy: np.ndarray, film_profile, *, include_base: bool = True) -> np.ndarray:
    """(..., 3) CMY dye densities -> (..., n_wl) spectral density on the simulation grid.

    ``include_base`` adds the film base/mask density (``film_profile.data.base_density``).
    """
    cmy = np.asarray(cmy, dtype=np.float64)
    lead = cmy.shape[:-1]
    flat = cmy.reshape(-1, 1, 3)
    base = film_profile.data.base_density if include_base else None
    d = compute_density_spectral(film_profile.data.channel_density, flat, base)
    return d.reshape(*lead, d.shape[-1])
