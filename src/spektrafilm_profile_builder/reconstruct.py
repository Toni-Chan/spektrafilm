"""Reconstruction of C, M, Y dye spectral densities of a colour negative from
the mid-scale neutral and minimum spectral densities that data sheets publish.

Port of the upstream ``profiles_factory.reconstruct`` ``dmid_dmin`` model
(spektrafilm history, commit 049f677^) to plain scipy (no lmfit). A generic
dye set is shifted, stretched and scaled, and masking-coupler Gaussians are
subtracted, so that

* C + M + Y matches (mid-scale neutral - minimum), and
* the minimum density is explained by base + Rayleigh-like scattering + fog
  + coloured masking couplers,

with an extra penalty on the off-diagonal densitometer crosstalk so that the
dyes stay as "pure" as the data allow.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import scipy.interpolate
import scipy.optimize

from .spectral import densitometer_crosstalk_matrix

# name: (initial, lower, upper)
_PARAMS = {
    'dye_amp0': (1.0, 0.5, 1.5), 'dye_amp1': (1.0, 0.5, 1.5), 'dye_amp2': (1.0, 0.5, 1.5),
    'dye_width0': (1.0, 0.9, 1.1), 'dye_width1': (1.0, 0.9, 1.1), 'dye_width2': (1.0, 0.9, 1.1),
    'dye_shift0': (0.0, -30, 30), 'dye_shift1': (0.0, -30, 30), 'dye_shift2': (0.0, -30, 30),
    'cpl_amp0': (0.1, 0.05, 0.5), 'cpl_amp1': (0.1, 0.05, 0.5), 'cpl_amp2': (0.1, 0.05, 0.5),
    'cpl_amp3': (0.03, 0.0, 0.5), 'cpl_amp4': (0.1, 0.05, 0.5),
    'cpl_width0': (20, 10, 40), 'cpl_width1': (20, 10, 40), 'cpl_width2': (20, 10, 40),
    'cpl_width3': (40, 10, 50), 'cpl_width4': (20, 10, 40),
    'cpl_max0': (435, 420, 450), 'cpl_max1': (560, 540, 600), 'cpl_max2': (475, 455, 490),
    'cpl_max3': (700, 650, 720), 'cpl_max4': (510, 495, 535),
    'dmax0': (2.3, 2.0, 5), 'dmax1': (2.3, 2.0, 5), 'dmax2': (2.3, 2.0, 5),
    'fog0': (0.07, 0.05, 0.10), 'fog1': (0.07, 0.05, 0.10), 'fog2': (0.07, 0.05, 0.10),
    'scat400': (0.65, 0.62, 1.0),
    'base': (0.05, 0.0, 0.15),
}
_NAMES = list(_PARAMS)
# the five coupler Gaussians: two subtract from cyan, two from magenta, one from yellow
_COUPLER_CHANNEL = [0, 0, 1, 1, 2]


@dataclass
class DyeReconstruction:
    dye_density: np.ndarray          # (n_wl, 3) C, M, Y, peak-normalised to 1
    dye_peak_density: np.ndarray     # (3,) peak density of each dye at mid-scale
    density_min_model: np.ndarray    # (n_wl,) simulated minimum density
    params: dict
    cost: float


def _shift_stretch(wl, spectrum, amp, width, shift, lam=100):
    center = wl[np.nanargmax(spectrum)]
    sel = np.isfinite(spectrum)
    sp = scipy.interpolate.make_smoothing_spline(wl[sel], spectrum[sel], lam=lam)
    out = sp((wl - center) / width + center + shift)
    sp = scipy.interpolate.make_smoothing_spline(wl, out, lam=lam)
    out = sp(wl)
    out[out < 0] = 0
    out[~sel] = np.nan
    return amp * out


def _model(p, wl, cmy_start):
    dye = np.stack([
        _shift_stretch(wl, cmy_start[:, i], p[f'dye_amp{i}'], p[f'dye_width{i}'], p[f'dye_shift{i}'])
        for i in range(3)], axis=1)
    cpl = np.stack([p[f'cpl_amp{i}'] * np.exp(-(wl - p[f'cpl_max{i}']) ** 2 / (2 * p[f'cpl_width{i}'] ** 2))
                    for i in range(5)], axis=1)
    cpl_cmy = np.zeros_like(dye)
    for i, ch in enumerate(_COUPLER_CHANNEL):
        cpl_cmy[:, ch] += cpl[:, i]
    cmy = dye - cpl_cmy
    # minimum density: masking couplers at full strength, fog, scattering, base
    dye_amp = np.array([p['dye_amp0'], p['dye_amp1'], p['dye_amp2']])
    dmax = np.array([p['dmax0'], p['dmax1'], p['dmax2']])
    fog = np.array([p['fog0'], p['fog1'], p['fog2']])
    mask_min = np.zeros_like(dye)
    for i, ch in enumerate(_COUPLER_CHANNEL):
        mask_min[:, ch] += cpl[:, i] / dye_amp[ch] * dmax[ch]
    scattering = -np.log10(np.clip(1 - p['scat400'] * 400 ** 4 / wl ** 4, 1e-3, None))
    dmin = np.sum(mask_min + fog * cmy, axis=1) + scattering + p['base']
    return cmy, dmin


def reconstruct_dye_density(wavelengths, density_mid, density_min, cmy_start, densitometer,
                            crosstalk_weight=2.0, min_weight=1.0, max_nfev=500, tol=5e-5):
    """Fit C, M, Y dye densities to published mid-scale/minimum densities.

    ``densitometer`` is used for the crosstalk penalty (status M for negatives).
    """
    wl = np.asarray(wavelengths, dtype=float)
    target = np.concatenate([density_mid - density_min, density_min])
    x0 = np.array([_PARAMS[n][0] for n in _NAMES], dtype=float)
    lb = np.array([_PARAMS[n][1] for n in _NAMES], dtype=float)
    ub = np.array([_PARAMS[n][2] for n in _NAMES], dtype=float)

    def residues(x):
        p = dict(zip(_NAMES, x))
        cmy, dmin = _model(p, wl, cmy_start)
        sim = np.concatenate([np.sum(cmy, axis=1), min_weight * dmin])
        res = target * np.r_[np.ones(wl.size), min_weight * np.ones(wl.size)] - sim
        res = np.nan_to_num(res)  # nan_policy='omit'
        xt = densitometer_crosstalk_matrix(densitometer, cmy).flatten()[[1, 2, 3, 5, 6, 7]]
        return np.concatenate([res, crosstalk_weight * xt])

    fit = scipy.optimize.least_squares(residues, x0, bounds=(lb, ub), method='trf',
                                       ftol=tol, xtol=tol, gtol=tol, max_nfev=max_nfev)
    p = dict(zip(_NAMES, fit.x))
    cmy, dmin = _model(p, wl, cmy_start)
    peak = np.nanmax(cmy, axis=0)
    return DyeReconstruction(dye_density=cmy / peak, dye_peak_density=peak,
                             density_min_model=dmin, params=p, cost=float(fit.cost))
