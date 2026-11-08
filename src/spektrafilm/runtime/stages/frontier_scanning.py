"""Simulated Fujifilm Frontier (SP500 / SP3000) film scanning.

Physical path: developed film CMY densities -> spectral density D(lambda)
-> per-channel narrowband capture through LED x filters x sensor QE
-> instrument RGB -> instrument density -> fixed positive rendering
-> output colour space. All physical constants come from the capture and
render profiles (``spektrafilm.model.scanner_profiles``).
"""
from __future__ import annotations

from typing import NewType

import warnings

import numpy as np

from spektrafilm.model.film_spectral import film_spectral_density
from spektrafilm.model.scanner_profiles import ScannerCaptureProfile

InstrumentRGB = NewType("InstrumentRGB", np.ndarray)


def film_valid_wavelengths(film_profile) -> np.ndarray:
    """Boolean mask of grid wavelengths where the film's dye and base data are defined."""
    cd = np.asarray(film_profile.data.channel_density, dtype=np.float64)
    bd = np.asarray(film_profile.data.base_density, dtype=np.float64)
    return np.all(np.isfinite(cd), axis=1) & np.isfinite(bd)


def capture_kernels(capture: ScannerCaptureProfile, valid: np.ndarray | None = None) -> np.ndarray:
    """Normalised per-channel kernels (n_wl, 3); each column sums to 1.

    ``valid`` restricts the kernels to wavelengths where film data exist;
    kernel weight outside is dropped (with a warning above 1%) rather than
    treated as opaque or clear film.
    """
    k = capture.channel_kernels().astype(np.float64)
    total = k.sum(axis=0)
    if valid is not None:
        k = np.where(valid[:, None], k, 0.0)
        lost = 1.0 - k.sum(axis=0) / np.where(total > 0, total, 1.0)
        if np.any(lost > 0.01):
            warnings.warn(
                f"capture profile {capture.id!r}: {np.round(lost * 100, 1)}% of R,G,B kernel weight "
                "falls where the film profile has no spectral data and is ignored",
                stacklevel=2,
            )
    s = k.sum(axis=0)
    if np.any(s <= 0):
        raise ValueError(f"capture profile {capture.id!r} has an empty channel kernel")
    return k / s


def capture_direct(cmy: np.ndarray, film_profile, capture: ScannerCaptureProfile) -> InstrumentRGB:
    """S_c = sum_l K_c(l) 10^-D(l) / sum_l K_c(l), for (..., 3) CMY input."""
    valid = film_valid_wavelengths(film_profile)
    d = film_spectral_density(cmy, film_profile, include_base=True)
    t = np.where(valid, 10.0 ** (-np.nan_to_num(d)), 0.0)
    return InstrumentRGB(t @ capture_kernels(capture, valid))


def capture_crosstalk_matrix(film_profile, capture: ScannerCaptureProfile) -> np.ndarray:
    """3x3 matrix M[c, j]: fraction of scanner channel c's kernel absorbed by dye j.

    Rows are scanner channels R, G, B; columns are dyes C, M, Y. Each dye's
    spectral density is normalised to unit peak, so a perfectly selective
    scanner gives a diagonal-dominant matrix.
    """
    k = capture_kernels(capture, film_valid_wavelengths(film_profile))
    dyes = np.asarray(film_profile.data.channel_density, dtype=np.float64)
    dyes = dyes / np.nanmax(dyes, axis=0)
    dyes = np.nan_to_num(dyes)
    return k.T @ dyes
