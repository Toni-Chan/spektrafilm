"""Characteristic-curve helpers: base+fog estimate, log-exposure anchoring and
the three-layer normal-CDF ("cdfs") model stored in spektrafilm profiles."""

from __future__ import annotations

import numpy as np
import scipy.optimize
import scipy.stats

SIGMA_FLOOR = 0.05  # same floor as spektrafilm.utils.morph_curves
MIDGRAY_TRANSMITTANCE = 0.184


def measure_density_min(log_exposure, density_curves, profile_type):
    """Base+fog per channel from a toe fit of the lowest fifth of each curve."""
    density_min = np.zeros(3)

    def curve_toe(e, k):
        gamma, e0, d0, c1 = k
        return gamma / c1 * np.log10(1 + 10 ** (c1 * (e - e0))) + d0

    k0 = (-1, 0, 0.05, -2) if profile_type == 'positive' else (1, 0, 0.05, 2)
    for i in range(3):
        data = np.array(density_curves[:, i], dtype=float)
        lo, hi = np.nanmin(data), np.nanmax(data)
        data[data > (hi - lo) / 5 + lo] = np.nan

        def residues(k):
            with np.errstate(over='ignore', invalid='ignore'):
                return np.nan_to_num(data - curve_toe(log_exposure, k))

        fit = scipy.optimize.least_squares(residues, k0)
        # never place base+fog above the lowest printed density
        density_min[i] = min(fit.x[2], lo)
    return density_min


def speed_point_log_exposure(log_exposure, density_curves, profile_type,
                             speed_point_density=0.2, stops_over_speed_point=3.0,
                             channel=1):
    """Log exposure of mid-grey, following the upstream profile conventions:

    * negative: green reaches ``speed_point_density`` over base+fog, mid-grey is
      ``stops_over_speed_point`` stops above that;
    * positive: green transmits 18.4 % over base+fog (D = 0.735).
    """
    d = np.array(density_curves[:, channel], dtype=float)
    d = d - np.nanmin(d)
    sel = np.isfinite(d)
    if profile_type == 'positive':
        target = np.log10(1 / MIDGRAY_TRANSMITTANCE)
        return float(np.interp(-target, -d[sel], log_exposure[sel]))
    le_speed = float(np.interp(speed_point_density, d[sel], log_exposure[sel]))
    return le_speed + np.log10(2 ** stops_over_speed_point)


def shift_curves(log_exposure, density_curves, shifts):
    """Shift each curve right by ``shifts[i]`` in log exposure: D'(x) = D(x - s)."""
    out = np.empty_like(density_curves)
    for i in range(density_curves.shape[1]):
        sel = np.isfinite(density_curves[:, i])
        out[:, i] = np.interp(log_exposure, log_exposure[sel] + shifts[i], density_curves[sel, i],
                              left=np.nan, right=np.nan)
    return out


# ----------------------------------------------------------------------------
# cdfs model: D(x) = sum_l A_l * Phi(+-(x - mu_l) / sigma_l)

def cdfs_layers(log_exposure, centers, amplitudes, sigmas, profile_type):
    sign = -1.0 if profile_type == 'positive' else 1.0
    x = np.asarray(log_exposure, dtype=float)[:, None]
    z = sign * (x - np.asarray(centers)[None, :]) / np.asarray(sigmas)[None, :]
    return scipy.stats.norm.cdf(z) * np.asarray(amplitudes)[None, :]


def _guess(loge, profile_type):
    m = np.mean(loge)
    lo, hi = np.min(loge), np.max(loge)
    if profile_type == 'positive':
        x0 = [m - 0.25, m, m + 0.25, 0.5, 1.0, 0.5, 0.2, 0.3, 0.5]
        lb = [lo, lo, lo, 0.25, 0.25, 0.25, SIGMA_FLOOR, SIGMA_FLOOR, SIGMA_FLOOR]
        ub = [hi, hi, hi, 5.0, 5.0, 5.0, 1.0, 1.0, 1.0]
    else:
        x0 = [m - 0.5, m, m + 0.5, 0.5, 0.5, 0.5, 0.3, 0.6, 0.9]
        lb = [lo, lo, lo, 0.2, 0.2, 0.2, SIGMA_FLOOR, SIGMA_FLOOR, SIGMA_FLOOR]
        ub = [hi, hi, hi, 1.35, 1.35, 1.35, 2.0, 2.0, 2.0]
    return np.array(x0), (np.array(lb), np.array(ub))


def fit_cdfs_channel(log_exposure, density, profile_type):
    sel = np.isfinite(density)
    loge, data = log_exposure[sel], density[sel]
    x0, bounds = _guess(loge, profile_type)

    def residues(x):
        return data - cdfs_layers(loge, x[0:3], x[3:6], x[6:9], profile_type).sum(axis=1)

    fit = scipy.optimize.least_squares(residues, x0, bounds=bounds)
    x = fit.x
    order = np.argsort(x[0:3])
    return x[0:3][order], x[3:6][order], x[6:9][order], float(np.sqrt(np.mean(fit.fun ** 2)))


def fit_cdfs(log_exposure, density_curves, profile_type):
    """Fit the 3-layer model to each channel. Returns (centers, amplitudes,
    sigmas) each shaped (3 channels, 3 layers) and the per-channel RMS."""
    centers, amplitudes, sigmas = np.zeros((3, 3)), np.zeros((3, 3)), np.zeros((3, 3))
    rms = np.zeros(3)
    for ch in range(3):
        c, a, s, r = fit_cdfs_channel(log_exposure, density_curves[:, ch], profile_type)
        centers[ch], amplitudes[ch], sigmas[ch], rms[ch] = c, a, s, r
    return centers, amplitudes, sigmas, rms


def evaluate_cdfs(log_exposure, centers, amplitudes, sigmas, profile_type):
    """Return (density_curves (n, 3), density_curves_layers (n, 3 layers, 3 channels))."""
    n = np.size(log_exposure)
    layers = np.zeros((n, 3, 3))
    for ch in range(3):
        layers[:, :, ch] = cdfs_layers(log_exposure, centers[ch], amplitudes[ch], sigmas[ch], profile_type)
    return layers.sum(axis=1), layers
