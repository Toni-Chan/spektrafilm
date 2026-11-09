"""Corrections that need the spektrafilm runtime: neutral enlarger filters and
the grey-ramp refinement of the characteristic curves.

Both follow the historical upstream profile factory (``profiles_factory.fitting``
and ``profiles_factory.correct``), ported to the current runtime API.
"""

from __future__ import annotations

import copy

import numpy as np
import scipy.optimize

from spektrafilm.profiles.io import Profile, load_profile
from spektrafilm.runtime.params_schema import RuntimePhotoParams
from spektrafilm.runtime.process import simulate

MIDGRAY = 0.184
_MIDGRAY_RGB = np.full((1, 1, 3), MIDGRAY)


def deterministic_params(film: Profile, print_profile: Profile | str,
                         illuminant: str = 'TH-KG3', filters_ymc=(55.0, 65.0, 0.0)) -> RuntimePhotoParams:
    """Runtime parameters for a deterministic, spatially flat linear-sRGB test."""
    if isinstance(print_profile, str):
        print_profile = load_profile(print_profile)
    params = RuntimePhotoParams(film=film, print=print_profile)
    params.io.input_color_space = 'sRGB'
    params.io.input_cctf_decoding = False
    params.io.output_color_space = 'sRGB'
    params.io.output_cctf_encoding = False
    params.debug.deactivate_spatial_effects = True
    params.debug.deactivate_stochastic_effects = True
    params.camera.auto_exposure = False
    params.settings.neutral_print_filters_from_database = False
    params.enlarger.illuminant = illuminant
    params.enlarger.y_filter_neutral = float(filters_ymc[0])
    params.enlarger.m_filter_neutral = float(filters_ymc[1])
    params.enlarger.c_filter_neutral = float(filters_ymc[2])
    return params


def render_midgray(film, print_profile, ev=0.0, scan_film=False, illuminant='TH-KG3',
                   filters_ymc=(55.0, 65.0, 0.0), print_exposure=1.0) -> np.ndarray:
    params = deterministic_params(film, print_profile, illuminant, filters_ymc)
    params.io.scan_film = scan_film
    params.camera.exposure_compensation_ev = float(ev)
    params.enlarger.print_exposure = float(print_exposure)
    return np.asarray(simulate(_MIDGRAY_RGB, params)).reshape(3)


def fit_neutral_print_filters(film: Profile, print_profile, illuminant='TH-KG3',
                              x0=(55.0, 65.0), c_filter=0.0, tol=1e-6):
    """Fit the Y and M enlarger filters (Kodak CC units, C fixed) and print
    exposure that print scene mid-grey as neutral 18.4 %. Returns
    ((C, M, Y), residual) in the order stored in ``neutral_print_filters.json``.
    """
    if isinstance(print_profile, str):
        print_profile = load_profile(print_profile)

    def residues(x):
        out = render_midgray(film, print_profile, illuminant=illuminant,
                             filters_ymc=(x[0], x[1], c_filter), print_exposure=x[2])
        return out - MIDGRAY

    best = None
    starts = [(x0[0], x0[1], 1.0), (50.0, 50.0, 1.0), (90.0, 90.0, 1.0), (20.0, 30.0, 1.0)]
    for start in starts:
        fit = scipy.optimize.least_squares(residues, start, bounds=([0, 0, 0.01], [250, 250, 20]),
                                           ftol=tol, xtol=tol, gtol=tol, method='trf')
        res = float(np.sum(np.abs(fit.fun)))
        if best is None or res < best[1]:
            best = (fit.x, res)
        if res < 1e-4:
            break
    x, res = best
    return (float(c_filter), float(x[1]), float(x[0])), res


def scale_shift_curves(log_exposure, density_curves, density_scale=(1, 1, 1), shift=(0, 0, 0)):
    dc = np.asarray(density_curves, dtype=float) * np.asarray(density_scale)[None, :]
    out = np.empty_like(dc)
    for i in range(3):
        out[:, i] = np.interp(log_exposure, log_exposure + shift[i], dc[:, i])
    return out


def grey_ramp_correction(film: Profile, print_profile=None, positive=False, data_trustability=0.3,
                         ev_ramp=None, filters_ymc=None, illuminant='TH-KG3'):
    """Fit per-channel density scales and R/B log-exposure shifts so that an
    exposure ramp of mid-grey renders neutral.

    Negative films are printed on ``print_profile`` with the enlarger exposure
    compensating the camera exposure (output should stay 18.4 % grey); positive
    films are scanned directly and only the colour balance along the ramp is
    fitted. ``data_trustability`` (0..1) weights a penalty on the density scales:
    1 keeps the data sheet curves almost untouched, 0 lets the ramp decide.
    Returns (density_scale (3,), shift (3,), rms_before, rms_after).
    """
    if ev_ramp is None:
        ev_ramp = [-1, 0, 1, 2] if positive else [-2, -1, 0, 1, 2, 3, 4, 5, 6]
    if print_profile is None:
        print_profile = 'kodak_portra_endura'
    if isinstance(print_profile, str):
        print_profile = load_profile(print_profile)
    if filters_ymc is None:
        filters_ymc = (55.0, 65.0, 0.0)
    le = film.data.log_exposure
    dc0 = np.array(film.data.density_curves, dtype=float)
    trial = film.clone()

    def ramp(x):
        trial.data.density_curves = scale_shift_curves(le, dc0, x[0:3], (x[3], 0.0, x[4]))
        out = np.array([render_midgray(trial, print_profile, ev=ev, scan_film=positive,
                                       illuminant=illuminant, filters_ymc=filters_ymc)
                        for ev in ev_ramp])
        if positive:
            mean = np.mean(out, axis=1, keepdims=True)
            return (out - mean) / mean * MIDGRAY
        return out - MIDGRAY

    def residues(x):
        res = ramp(x).ravel()
        bias = 2.0 * (np.asarray(x[0:3]) - 1.0) * data_trustability
        return np.concatenate([res, bias])

    x0 = np.array([1.0, 1.0, 1.0, 0.0, 0.0])
    before = float(np.sqrt(np.mean(ramp(x0) ** 2)))
    fit = scipy.optimize.least_squares(residues, x0, bounds=([0.5, 0.5, 0.5, -1, -1], [1.5, 1.5, 1.5, 1, 1]),
                                       diff_step=1e-3)
    after = float(np.sqrt(np.mean(ramp(fit.x) ** 2)))
    return fit.x[0:3], np.array([fit.x[3], 0.0, fit.x[4]]), before, after


def positive_scan_exposure_shift(film: Profile, illuminant='TH-KG3', bracket=(-1.0, 1.0)) -> float:
    """Common log-exposure shift of the density curves that makes a scanned
    reversal film render scene mid-grey as 18.4 % (green), the convention of the
    shipped positive profiles (they all scan mid-grey to ~0.18 at 0 EV)."""
    le = film.data.log_exposure
    dc0 = np.array(film.data.density_curves, dtype=float)
    trial = film.clone()

    def g(s):
        trial.data.density_curves = scale_shift_curves(le, dc0, (1, 1, 1), (s, s, s))
        return render_midgray(trial, 'kodak_portra_endura', ev=0.0, scan_film=True,
                              illuminant=illuminant)[1] - MIDGRAY

    return float(scipy.optimize.brentq(g, *bracket, xtol=1e-4))
