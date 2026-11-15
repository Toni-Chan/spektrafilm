"""Spectral/exposure grids, interpolation helpers and bundled reference data
(densitometer responsivities, generic dye set)."""

from __future__ import annotations

import importlib.resources as pkg_resources
from pathlib import Path

import numpy as np
import scipy.interpolate

from spektrafilm.config import LOG_EXPOSURE, SPECTRAL_SHAPE

WAVELENGTHS = np.asarray(SPECTRAL_SHAPE.wavelengths, dtype=float)
LOG_EXPOSURE_GRID = np.asarray(LOG_EXPOSURE, dtype=float)

_DATA = 'spektrafilm_profile_builder.data'


def read_xy_csv(path) -> np.ndarray:
    """Read a headerless ``x, y`` CSV into a (2, n) array sorted by x, unique x."""
    data = np.loadtxt(path, delimiter=',', ndmin=2)
    x, y = data[:, 0], data[:, 1]
    order = np.argsort(x, kind='stable')
    x, y = x[order], y[order]
    x, idx = np.unique(x, return_index=True)
    return np.vstack([x, y[idx]])


def interpolate(xy: np.ndarray, new_x: np.ndarray, method: str = 'akima') -> np.ndarray:
    """Interpolate (2, n) data on ``new_x``; NaN outside the data range."""
    x, y = xy
    new_x = np.asarray(new_x, dtype=float)
    if method == 'akima' and x.size >= 3:
        out = scipy.interpolate.Akima1DInterpolator(x, y, extrapolate=False)(new_x)
    else:
        out = np.interp(new_x, x, y, left=np.nan, right=np.nan)
    return np.asarray(out, dtype=float)


def extrapolate_log_sensitivity_tails(wavelengths, log_sensitivity, edge_nm=15.0, width_nm=30.0,
                                      slope_min=0.01, slope_max=0.08):
    """Fill NaN tails of log-sensitivity curves with a smooth, monotonically
    decaying extension.

    Data sheets only print the top ~1.5-2 log units of each curve. The runtime
    needs finite sensitivities on the whole 380-780 nm grid, so the tails are
    continued as ``ls_edge - k * w * log(1 + d / w)``: the initial slope ``k``
    is the edge slope of the printed curve (clipped to [slope_min, slope_max]
    log10/nm) and it relaxes logarithmically with the distance ``d`` from the
    edge. These tails are far below the printed range and only matter for
    extreme, saturated spectra.
    """
    wl = np.asarray(wavelengths, dtype=float)
    out = np.array(log_sensitivity, dtype=float, copy=True)
    for ch in range(out.shape[1]):
        y = out[:, ch]
        ok = np.isfinite(y)
        if not ok.any():
            raise ValueError('log sensitivity channel without data')
        i0, i1 = np.flatnonzero(ok)[[0, -1]]
        # left tail
        sel = ok & (wl <= wl[i0] + edge_nm)
        k = _edge_slope(wl[sel], y[sel], sign=+1, slope_min=slope_min, slope_max=slope_max)
        d = wl[i0] - wl[:i0]
        y[:i0] = y[i0] - k * width_nm * np.log1p(d / width_nm)
        # right tail
        sel = ok & (wl >= wl[i1] - edge_nm)
        k = _edge_slope(wl[sel], y[sel], sign=-1, slope_min=slope_min, slope_max=slope_max)
        d = wl[i1 + 1:] - wl[i1]
        y[i1 + 1:] = y[i1] - k * width_nm * np.log1p(d / width_nm)
        out[:, ch] = y
    return out


def _edge_slope(x, y, sign, slope_min, slope_max):
    if x.size >= 2:
        slope = np.polyfit(x, y, 1)[0] * sign  # positive when rising away from the tail
    else:
        slope = slope_min
    return float(np.clip(slope, slope_min, slope_max))


def _data_path(*parts) -> Path:
    return Path(str(pkg_resources.files(_DATA).joinpath(*parts)))


def load_densitometer(kind: str = 'status_M', wavelengths=WAVELENGTHS) -> np.ndarray:
    """Densitometer spectral responsivities (n_wl, 3) RGB, each normalised to unit sum."""
    resp = np.zeros((np.size(wavelengths), 3))
    for i, ch in enumerate('rgb'):
        xy = read_xy_csv(_data_path('densitometer', kind, f'responsivity_{ch}.csv'))
        resp[:, i] = np.interp(wavelengths, xy[0], xy[1], left=0.0, right=0.0)
    resp[resp < 0] = 0
    resp /= np.nansum(resp, axis=0)
    return resp


def load_generic_dyes(name: str = 'generic_a', wavelengths=WAVELENGTHS) -> np.ndarray:
    """Generic C, M, Y dye spectral densities (n_wl, 3), used as the starting
    point when a data sheet only publishes mid-scale/minimum densities."""
    dyes = np.zeros((np.size(wavelengths), 3))
    for i, ch in enumerate('cmy'):
        xy = read_xy_csv(_data_path('dyes', name, f'dye_density_{ch}.csv'))
        dyes[:, i] = interpolate(xy, wavelengths)
    return dyes


def densitometer_crosstalk_matrix(densitometer, dye_density) -> np.ndarray:
    """M[i, j] = status density read by densitometer channel i (R, G, B) of unit
    amount of dye j (C, M, Y)."""
    m = np.zeros((3, 3))
    # missing dye data (outside the printed range) counts as zero density
    transmittance = 10 ** (-np.nan_to_num(np.asarray(dye_density, dtype=float)[:, 0:3]))
    for i in range(3):
        for j in range(3):
            m[i, j] = -np.log10(np.nansum(densitometer[:, i] * transmittance[:, j])
                                / np.nansum(densitometer[:, i]))
    return m


def fill_dye_gaps(wavelengths, dyes, decay_nm: float = 25.0) -> np.ndarray:
    """Continue each dye curve over the wavelength range covered by *any* dye.

    The runtime treats NaN spectral density as opaque (``density_to_light`` sets
    the transmittance to zero), so a dye drawn over a shorter range than the
    others (e.g. a yellow dye printed only up to 600 nm) would black out that
    part of the spectrum. Inside the union of the published ranges, missing
    values are continued from the last published value with an exponential
    decay; outside the union all dyes stay NaN, as in the shipped profiles.
    """
    wl = np.asarray(wavelengths, dtype=float)
    out = np.array(dyes, dtype=float, copy=True)
    finite_any = np.any(np.isfinite(out), axis=1)
    if not finite_any.any():
        return out
    lo, hi = np.flatnonzero(finite_any)[[0, -1]]
    for j in range(out.shape[1]):
        idx = np.flatnonzero(np.isfinite(out[:, j]))
        if idx.size == 0:
            out[lo:hi + 1, j] = 0.0
            continue
        first, last = idx[0], idx[-1]
        for k in range(lo, first):
            out[k, j] = out[first, j] * np.exp(-(wl[first] - wl[k]) / decay_nm)
        for k in range(last + 1, hi + 1):
            out[k, j] = out[last, j] * np.exp(-(wl[k] - wl[last]) / decay_nm)
    return out


def extend_dyes_beyond_sheet(wavelengths, dyes, decay_nm: float = 25.0) -> np.ndarray:
    """ESTIMATE placeholder: continue dye curves outside the range the sheet prints.

    ``fill_dye_gaps`` leaves every dye NaN (opaque in the runtime) outside the
    union of the printed ranges. Sheets that stop at 420 nm (Kodak E-55) would
    then black out 380-420 nm. Opt-in (recipe ``dye_extension = hold_decay``):
    on the short-wavelength side each dye holds its first printed value (dyes
    keep absorbing towards the UV; no data), on the long side it decays
    exponentially from its last printed value (``decay_nm``). Not data; only
    matters for light at the ends of the visible range.
    """
    wl = np.asarray(wavelengths, dtype=float)
    out = fill_dye_gaps(wl, dyes, decay_nm=decay_nm)
    finite_any = np.any(np.isfinite(out), axis=1)
    if not finite_any.any():
        return out
    lo, hi = np.flatnonzero(finite_any)[[0, -1]]
    for j in range(out.shape[1]):
        out[:lo, j] = out[lo, j]
        out[hi + 1:, j] = out[hi, j] * np.exp(-(wl[hi + 1:] - wl[hi]) / decay_nm)
    return out
