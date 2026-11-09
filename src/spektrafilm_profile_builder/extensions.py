"""Profile-extension sidecars for Fuji's 4th colour layer.

Fujifilm REALA / PRO / X-TRA / nexia negatives carry a fourth, cyan-sensitive
emulsion layer (peak ~515-520 nm) that forms no image dye: its development
releases DIR inhibitor into the red-sensitive layer, so blue-green light
*lowers* the red record, giving the red channel an effective negative
spectral lobe like the CIE r-bar colour-matching function.

The Pro Data Guide prints that layer's spectral sensitivity
(``log_sensitivity_cyan_layer.csv`` in the raw records). It cannot go into the
profile JSON (shared format, see ``spektrafilm.profiles.extensions``), so this
module writes a sidecar ``spektrafilm/data/profile_extensions/<stock>.json``
that the fork's runtime picks up.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import scipy.optimize

from spektrafilm.profiles.extensions import (
    EXTENSION_SCHEMA_VERSION, InhibitorLayer, ProfileExtension, profile_extension_to_dict,
)

from .records import RawRecord
from .spectral import WAVELENGTHS, extrapolate_log_sensitivity_tails

# CIE 1931 (Wright & Guild) r-bar: min -0.09356 at 515 nm, max 0.34756 at 605 nm.
CIE_RBAR_NEGATIVE_LOBE_RATIO = 0.09356 / 0.34756   # = 0.269

AMOUNT_LABEL = 'estimate'
AMOUNT_BASIS = (
    'Estimate, not measured: the data sheet gives the layer\'s spectral sensitivity but not how '
    'strongly it inhibits. The runtime lowers red log exposure by '
    'amount * [D(log E_cyan) - D(log E_green)] (departure from neutral; D = red characteristic '
    'curve shape). amount_default is the value for which the effective red spectral sensitivity '
    'of the full film model (narrowband sweep on mid-grey through spektrafilm.model.develop, '
    'default negative DIR-coupler matrix) has a negative lobe at 500-530 nm as deep, relative to '
    'its positive peak, as the CIE 1931 r-bar colour-matching function (0.0936 / 0.3476 = 0.269, '
    'minimum at 515 nm). Fujifilm describes the 4th layer as giving film the negative red '
    'response of human vision around 500-520 nm. The generic DIR couplers alone already give a '
    'shallower lobe (effective_red_lobe_ratio_without_layer).'
)


def _midgray_raw_single(sensitivity, reference_illuminant):
    from spektrafilm.utils.spectral_upsampling import rgb_to_raw_hanatos2025
    sens = np.tile(np.asarray(sensitivity, dtype=float)[:, None], (1, 3))
    raw = rgb_to_raw_hanatos2025(np.full((1, 1, 3), 0.184), sens, color_space='sRGB',
                                 apply_cctf_decoding=False, reference_illuminant=reference_illuminant)
    return float(np.asarray(raw).reshape(3)[0])


def cyan_layer_log_sensitivity(record: RawRecord, reference_illuminant: str) -> np.ndarray:
    """Cyan-layer log sensitivity on the profile grid, tails continued, normalised
    so that 18.4 % grey under ``reference_illuminant`` gives raw exposure 1.

    The sheet's sensitivity zero point is relative (the 4 curves share one
    plot, with a 1.0 bracket and no axis numbers); the normalisation removes it,
    as it does for R, G, B.
    """
    ls = record.log_sensitivity_cyan_layer
    if ls is None:
        raise ValueError(f'{record.folder}: no log_sensitivity_cyan_layer.csv')
    # The sheet prints only the top ~0.5 log units of this narrow band, so the
    # tails are continued more steeply than the R, G, B defaults (>= 0.03
    # log10/nm, slower relaxation): a band-limited layer, not a broad tail.
    ls = extrapolate_log_sensitivity_tails(WAVELENGTHS, np.asarray(ls, dtype=float)[:, None],
                                           width_nm=60.0, slope_min=0.03, slope_max=0.1)[:, 0]
    raw = _midgray_raw_single(np.nan_to_num(10 ** ls), reference_illuminant)
    return ls - np.log10(raw)


def red_gamma_at_midgray(profile) -> float:
    le = np.asarray(profile.data.log_exposure, dtype=float)
    dc = np.asarray(profile.data.density_curves, dtype=float)[:, 0]
    return float(np.interp(0.0, le, np.gradient(dc, le)))


def effective_red_sensitivity(red_log_sensitivity, green_log_sensitivity, cyan_log_sensitivity,
                              gamma_r, amount) -> np.ndarray:
    """Linearised effective red sensitivity s_r - A gamma_r (s_c - s_g) around mid-grey."""
    s_r = np.nan_to_num(10 ** np.asarray(red_log_sensitivity, dtype=float))
    s_g = np.nan_to_num(10 ** np.asarray(green_log_sensitivity, dtype=float))
    s_c = np.nan_to_num(10 ** np.asarray(cyan_log_sensitivity, dtype=float))
    return s_r - amount * gamma_r * (s_c - s_g)


def default_amount(red_log_sensitivity, green_log_sensitivity, cyan_log_sensitivity, gamma_r,
                   target_ratio: float = CIE_RBAR_NEGATIVE_LOBE_RATIO) -> float:
    """Amount A with min(eff) / max(eff) = -target_ratio, eff = s_r - A gamma_r (s_c - s_g)."""

    def f(a):
        eff = effective_red_sensitivity(red_log_sensitivity, green_log_sensitivity,
                                        cyan_log_sensitivity, gamma_r, a)
        return np.min(eff) / np.max(eff) + target_ratio

    return float(scipy.optimize.brentq(f, 0.0, 50.0))


def _negative_dir_couplers(profile):
    """DIR-coupler params the runtime uses for this profile (stock specifics applied)."""
    from dataclasses import replace
    from spektrafilm.runtime.params_builder import _apply_film_specifics
    from spektrafilm.runtime.params_schema import RuntimePhotoParams
    params = RuntimePhotoParams(film=profile, print=profile)
    params = _apply_film_specifics(params)
    # per-pixel evaluation: no inhibitor diffusion
    return replace(params.film_render.dir_couplers, diffusion_size_um=0.0)


def model_effective_red_sensitivity(profile, cyan_log_sensitivity, amount, dir_couplers=None,
                                    delta_frac: float = 0.01) -> np.ndarray:
    """Effective red spectral sensitivity of the film model around mid-grey.

    Narrowband sweep: for every wavelength bin a small energy ``delta`` is added
    to an 18.4 % grey spectrum of the reference illuminant; the red density
    from :func:`spektrafilm.model.develop.develop` (DIR couplers and the
    inhibitor layer, no grain) is converted back to the log exposure the red
    data curve would need for it, per unit added energy.
    """
    from spektrafilm.model.couplers import InhibitorExposure
    from spektrafilm.model.develop import develop
    from spektrafilm.model.illuminants import standard_illuminant
    from spektrafilm.runtime.params_schema import GrainParams

    dc = _negative_dir_couplers(profile) if dir_couplers is None else dir_couplers
    data = profile.data
    illum = standard_illuminant(profile.info.reference_illuminant)
    sens = np.nan_to_num(10 ** np.asarray(data.log_sensitivity, dtype=float))
    s_c = np.nan_to_num(10 ** np.asarray(cyan_log_sensitivity, dtype=float))
    grey = illum * 0.184
    norm = grey @ sens
    norm_c = grey @ s_c
    n = WAVELENGTHS.size
    delta = delta_frac * np.sum(grey)
    spectra = np.tile(grey, (n + 1, 1))
    spectra[np.arange(n), np.arange(n)] += delta     # last row: plain grey
    raw = (spectra @ sens) / norm
    raw_c = (spectra @ s_c) / norm_c
    log_raw = np.log10(raw)[None]
    inhibitor = InhibitorExposure(log_raw=np.log10(raw_c)[None], amount=float(amount), target=0, reference=1)
    le = np.asarray(data.log_exposure, dtype=float)
    curves = np.asarray(data.density_curves, dtype=float)
    density = develop(log_raw, None, le, curves, data.density_curves_layers, dc, GrainParams(active=False),
                      profile.info.type, bypass_grain=True, inhibitor=inhibitor)
    ncurve = curves[:, 0] - np.nanmin(curves[:, 0])
    log_e_eff = np.interp(density[0, :, 0], ncurve, le)
    return (log_e_eff[:n] - log_e_eff[n]) * np.log(10) / delta


LOBE_BAND_NM = (500.0, 530.0)


def lobe_ratio(eff, band_nm=LOBE_BAND_NM) -> float:
    """Depth of the effective red response around the CIE r-bar minimum
    (500-530 nm; r-bar is lowest at 515 nm, where the cyan layer also peaks)
    relative to its positive peak (400-700 nm). The band is kept narrow so
    that blue-region dips caused by the generic B->R DIR coupler (deep for
    narrow red sensitivities such as NPL's) do not count as the cyan lobe."""
    band = (WAVELENGTHS >= band_nm[0]) & (WAVELENGTHS <= band_nm[1])
    vis = (WAVELENGTHS >= 400.0) & (WAVELENGTHS <= 700.0)
    return float(np.min(eff[band]) / np.max(eff[vis]))


def calibrate_amount(profile, cyan_log_sensitivity, target_ratio: float = CIE_RBAR_NEGATIVE_LOBE_RATIO,
                     max_amount: float = 5.0) -> tuple[float, float]:
    """Amount whose model effective-red lobe ratio is ``-target_ratio``.

    Returns (amount, lobe ratio without the layer)."""
    dc = _negative_dir_couplers(profile)

    def f(a):
        return lobe_ratio(model_effective_red_sensitivity(profile, cyan_log_sensitivity, a, dc)) + target_ratio

    f0 = f(0.0)
    ratio_off = f0 - target_ratio
    if f0 <= 0:
        return 0.0, ratio_off
    if f(max_amount) > 0:
        return max_amount, ratio_off
    return float(scipy.optimize.brentq(f, 0.0, max_amount, xtol=1e-4)), ratio_off


def build_cyan_layer_extension(record: RawRecord, profile, amount: float | None = None,
                               source: str = '') -> ProfileExtension:
    ref = profile.info.reference_illuminant
    ls_c = cyan_layer_log_sensitivity(record, ref)
    ls_r = np.asarray(profile.data.log_sensitivity, dtype=float)[:, 0]
    ls_g = np.asarray(profile.data.log_sensitivity, dtype=float)[:, 1]
    gamma_r = red_gamma_at_midgray(profile)
    a_linear = default_amount(ls_r, ls_g, ls_c, gamma_r)
    a_model, ratio_off = calibrate_amount(profile, ls_c)
    a = a_model if amount is None else float(amount)
    raw_ls = record.log_sensitivity_cyan_layer
    raw_r = record.log_sensitivity[:, 0]
    rel_peak = float(np.nanmax(raw_ls) - np.nanmax(raw_r))
    finite = np.isfinite(raw_ls)
    printed = [float(WAVELENGTHS[finite][0]), float(WAVELENGTHS[finite][-1])]
    peak_nm = float(WAVELENGTHS[np.nanargmax(np.where(finite, raw_ls, -np.inf))])
    layer = InhibitorLayer(
        name='cyan', target='r', reference='g', wavelengths=WAVELENGTHS.copy(), log_sensitivity=ls_c,
        amount_default=round(a, 4), label=AMOUNT_LABEL,
        source=source or f'{record.name}: log_sensitivity_cyan_layer.csv ({record.folder.name})',
        notes=('Fujifilm 4th colour layer: cyan-sensitive, forms no image dye, releases DIR '
               'inhibitor into the red-sensitive layer. log_sensitivity is normalised to raw '
               'exposure 1 at 18.4 % grey under the reference illuminant; values outside the '
               'printed range are a smooth extrapolation. The runtime models the developed '
               "silver of this layer with the red layer's characteristic-curve shape."),
        extra={
            'amount_basis': AMOUNT_BASIS,
            'gamma_r_at_midgray': round(gamma_r, 4),
            'effective_red_lobe_ratio_without_layer': round(ratio_off, 4),
            'effective_red_lobe_ratio_target': round(-CIE_RBAR_NEGATIVE_LOBE_RATIO, 4),
            'amount_linearised_without_dir_couplers': round(a_linear, 4),
            'reference_illuminant': ref,
            'printed_range_nm': printed,
            'printed_peak_nm': peak_nm,
            'printed_peak_log_sensitivity_relative_to_red_peak': round(rel_peak, 4),
        },
    )
    return ProfileExtension(stock=profile.info.stock, version=EXTENSION_SCHEMA_VERSION,
                            inhibitor_layers=(layer,))


def extension_to_json(ext: ProfileExtension) -> str:
    d = profile_extension_to_dict(ext)
    for layer in d['inhibitor_layers']:
        layer['log_sensitivity'] = [None if v is None else round(v, 5) for v in layer['log_sensitivity']]
    text = json.dumps(d, indent=2, ensure_ascii=False)
    # keep numeric arrays on one line each
    return re.sub(r'\[\s*([-0-9.,\s enul]+?)\s*\]',
                  lambda m: '[' + ', '.join(x.strip() for x in m.group(1).split(',')) + ']', text)


def save_extension_json(ext: ProfileExtension, out_dir) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f'{ext.stock}.json'
    path.write_text(extension_to_json(ext) + '\n', encoding='utf-8')
    return path
