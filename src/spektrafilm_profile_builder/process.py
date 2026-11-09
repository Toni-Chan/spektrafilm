"""Raw record -> processed spektrafilm profile."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date

import numpy as np
import scipy.ndimage
import scipy.optimize

from spektrafilm.profiles.io import (
    DensityCurvesModel, Profile, ProfileData, ProfileInfo, ProfileMetadata, list_profiles, load_profile,
)
from spektrafilm.utils.spectral_upsampling import rgb_to_raw_hanatos2025

from . import __version__
from .curves import (
    MIDGRAY_TRANSMITTANCE, evaluate_cdfs, fit_cdfs, measure_density_min, shift_curves, speed_point_log_exposure,
)
from .reconstruct import reconstruct_dye_density
from .records import RawRecord
from .runtime_fit import (
    fit_neutral_print_filters, grey_ramp_correction, positive_scan_exposure_shift, scale_shift_curves,
)
from .spectral import (
    LOG_EXPOSURE_GRID, densitometer_crosstalk_matrix, extrapolate_log_sensitivity_tails,
    fill_dye_gaps, interpolate, load_densitometer, load_generic_dyes,
)


@dataclass
class Recipe:
    """How to turn one raw record into a profile. Every field maps to a CLI flag
    or a column of a batch recipe file."""
    stock: str
    name: str
    type: str = 'negative'                     # 'negative' | 'positive' | 'paper'
    support: str | None = None                 # paper only: 'paper' (reflection, default) or 'film' (display transparency)
    densitometer: str | None = None            # default: status_M (negative) / status_A (positive)
    log_sensitivity_density_over_min: float = 1.0
    reference_illuminant: str = 'D55'
    viewing_illuminant: str = 'D50'
    target_print: str | None = None            # paper profile id (negatives)
    use: str = 'still'
    antihalation: str = 'strong'
    dye_start: str = 'generic_a'               # generic dyes used to start the negative reconstruction
    grey_ramp_correction: bool = True
    data_trustability: float = 0.3
    adaptation_donors: list = field(default_factory=list)  # shipped profiles whose hanatos2025 params are averaged
    datasource: str = ''                       # appended to the metadata datasource text
    copyright: str = ''


@dataclass
class BuildReport:
    stock: str
    type: str
    steps: list = field(default_factory=list)

    def log(self, msg):
        self.steps.append(msg)


# -----------------------------------------------------------------------------
# helpers

def _density_curves_on_grid(record: RawRecord):
    xg = record.density_curves_xy[1][0]
    shift = (np.max(xg) + np.min(xg)) / 2
    le = LOG_EXPOSURE_GRID.copy()
    dc = np.stack([interpolate(xy, le + shift) for xy in record.density_curves_xy], axis=1)
    return le, dc


def _midgray_raw(log_sensitivity, reference_illuminant):
    sens = np.nan_to_num(10 ** np.asarray(log_sensitivity, dtype=float))
    raw = rgb_to_raw_hanatos2025(np.full((1, 1, 3), 0.184), sens, color_space='sRGB',
                                 apply_cctf_decoding=False, reference_illuminant=reference_illuminant)
    return np.asarray(raw).reshape(3)


def normalize_sensitivity(log_exposure, log_sensitivity, density_curves, reference_illuminant,
                          compensate_with_curve_shift=False):
    """Scale each channel's sensitivity so that mid-grey (18.4 % sRGB grey lit by
    the reference illuminant, hanatos2025 spectral upsampling) gives raw
    exposure 1, which is what the runtime expects.

    Data-sheet characteristic curves are measured with white light and plotted
    against the same log H for the three layers, so after this normalisation
    log exposure 0 is mid-grey in every channel and the curves need no
    per-channel shift; the printed sensitivity zero point (relative only on
    negative sheets) drops out. ``compensate_with_curve_shift=True`` reproduces
    the historical factory instead (curves shifted by the R/B balance factors,
    i.e. treating the printed sensitivity levels as absolute).
    """
    raw = _midgray_raw(log_sensitivity, reference_illuminant)
    ls = np.asarray(log_sensitivity) - np.log10(raw)[None, :]
    corr = raw[1] / raw
    dc = density_curves
    if compensate_with_curve_shift:
        dc = shift_curves(log_exposure, density_curves, np.log10(corr))
    return ls, dc, corr


def _fit_and_eval(le, dc, profile_type):
    centers, amps, sigmas, rms = fit_cdfs(le, dc, profile_type)
    curves, layers = evaluate_cdfs(le, centers, amps, sigmas, profile_type)
    return curves, layers, DensityCurvesModel('cdfs', centers, amps, sigmas), rms


def _anchor(le, dc, profile_type):
    le0 = speed_point_log_exposure(le, dc, profile_type)
    return shift_curves(le, dc, [-le0] * 3), le0


def _hanatos_params(donors, profile_type, stock=''):
    """Average the hanatos2025 adaptation parameters (spectral window and
    exposure-correction surface) of shipped profiles of the same type. These
    parameters are fitted by upstream's private profile creator; a data sheet
    does not constrain them, so they are borrowed (default: shipped film
    profiles of the same maker and type, else all shipped film profiles of
    that type)."""
    shipped = list_profiles()
    if donors:
        candidates = [list(donors)]
    else:
        maker = stock.split('_')[0] + '_'
        candidates = [[s for s in shipped if s.startswith(maker)], shipped]
    for group in candidates:
        win, surf, used = [], [], []
        for s in group:
            p = load_profile(s)
            if p.info.support != 'film' or p.info.type != profile_type:
                continue
            w = np.asarray(p.data.hanatos2025_adaptation_window_params, dtype=float)
            sf = np.asarray(p.data.hanatos2025_adaptation_surface_params, dtype=float)
            if w.size == 0 or sf.size == 0:
                continue
            win.append(w); surf.append(sf); used.append(s)
        if used:
            return np.mean(win, axis=0), np.mean(surf, axis=0), used
    return np.empty((0,)), np.empty((0, 3)), []


def _positive_base_density(wl, dc_min, sigma_nm=20.0):
    # status A peaks (B, G, R) -> spectral base+fog, as the upstream factory did
    smin = np.interp(wl, [445, 530, 610], np.flip(dc_min))
    return scipy.ndimage.gaussian_filter1d(smin, sigma_nm / np.mean(np.diff(wl)))


# -----------------------------------------------------------------------------
# main entry point

def _metameric_neutral_scale(cmy, base, viewing_illuminant, midgray=MIDGRAY_TRANSMITTANCE):
    """Upstream ``balance_metameric_neutral``: dye amounts (C, M, Y) whose
    mixture plus base renders as an 18.4 % neutral under the viewing
    illuminant (CIE 1931 2 deg, sRGB primaries with the illuminant white).
    Returns the amounts and the mid-scale spectral density."""
    import colour
    from colour.models import RGB_COLOURSPACE_sRGB
    from spektrafilm.config import STANDARD_OBSERVER_CMFS
    from spektrafilm.model.illuminants import standard_illuminant

    ill = np.asarray(standard_illuminant(viewing_illuminant)[:], dtype=float)
    cmfs = np.asarray(STANDARD_OBSERVER_CMFS[:], dtype=float)
    norm = np.sum(ill * cmfs[:, 1])
    ill_xy = colour.XYZ_to_xy(ill @ cmfs / norm)
    dyes = np.nan_to_num(cmy)

    def rgb(d):
        mid = dyes @ d + base
        light = np.nan_to_num(10 ** (-mid) * ill)
        return colour.XYZ_to_RGB(light @ cmfs / norm, RGB_COLOURSPACE_sRGB, illuminant=ill_xy,
                                 apply_cctf_encoding=False)

    fit = scipy.optimize.least_squares(lambda d: rgb(d) - midgray, [0.5, 0.5, 0.5], bounds=(0, 5))
    return fit.x, cmy @ fit.x + base


def _visual_midgray_log_exposure(le, dc, cmy, base, viewing_illuminant, midgray=MIDGRAY_TRANSMITTANCE):
    """Log exposure at which the print's spectral density (dyes @ layer density
    + base) gives ``midgray`` luminance (CIE Y) under the viewing illuminant."""
    from spektrafilm.config import STANDARD_OBSERVER_CMFS
    from spektrafilm.model.illuminants import standard_illuminant

    w = np.asarray(standard_illuminant(viewing_illuminant)[:], dtype=float) * \
        np.asarray(STANDARD_OBSERVER_CMFS[:], dtype=float)[:, 1]
    dens = np.nan_to_num(np.asarray(dc, dtype=float)) @ np.nan_to_num(cmy).T + base[None, :]
    y = (10 ** -dens) @ w / w.sum()
    sel = np.isfinite(y)
    return float(np.interp(-np.log10(midgray), -np.log10(y[sel]), le[sel]))


def build_paper_profile(record: RawRecord, recipe: Recipe, report: BuildReport | None = None) -> Profile:
    """Colour print paper / print material (stage 'printing'), following the
    upstream ``process_paper_profile``: base+fog spread spectrally from the
    status-A minima, log exposure first put where green reaches D = 0.735 over
    D-min, dyes scaled so that the mid-scale neutral is metameric to 18.4 % grey
    under the viewing illuminant (relative to green), status-A unmixing, cdfs
    fit; finally log exposure 0 is moved to where the print renders 18.4 %
    luminance under the viewing illuminant (the level the shipped papers print
    mid-grey at).
    The sheet's spectral sensitivities are kept as printed (their R/G/B levels
    set the enlarger filtration; the absolute level cancels in the runtime's
    print-exposure normalisation); tails are continued so they are finite."""
    report = report or BuildReport(recipe.stock, 'paper')
    densitometer_kind = recipe.densitometer or 'status_A'
    dstm = load_densitometer(densitometer_kind)
    wl = record.wavelengths
    if not record.has_cmy_dyes:
        raise ValueError(f'{record.folder}: a paper needs dye_density_c/m/y.csv')

    ls = extrapolate_log_sensitivity_tails(wl, record.log_sensitivity)

    le, dc = _density_curves_on_grid(record)
    dc_min = measure_density_min(le, dc, 'negative')
    dc = dc - dc_min
    le0 = speed_point_log_exposure(le, dc, 'negative', speed_point_density=np.log10(1 / MIDGRAY_TRANSMITTANCE),
                                   stops_over_speed_point=0.0)
    dc = shift_curves(le, dc, [-le0] * 3)
    base = _positive_base_density(wl, dc_min)
    report.log(f'base+fog (status A) RGB: {np.round(dc_min, 3).tolist()}; green D=0.735 over D-min at log H {le0:+.3f}')

    cmy = fill_dye_gaps(wl, record.dye_density_cmy)
    # peak-normalise on the visible absorption band: paper sheets draw every dye
    # rising into the UV (overcoat UV absorber), which must not set the scale
    vis = (wl >= 420) & (wl <= 700)
    cmy = cmy / np.nanmax(cmy[vis], axis=0)
    d_mid, mid = _metameric_neutral_scale(cmy, base, recipe.viewing_illuminant)
    cmy = cmy * (d_mid / d_mid[1])[None, :]
    mid = np.where(np.isfinite(mid), mid, np.nan)
    report.log(f'metameric neutral ({recipe.viewing_illuminant}) dye amounts CMY {np.round(d_mid, 4).tolist()}')

    m = densitometer_crosstalk_matrix(dstm, cmy)
    dc = np.einsum('ij,kj->ki', np.linalg.inv(m), dc)
    dc = np.where(np.isfinite(dc), np.clip(dc, 0, None), np.nan)
    report.log(f'densitometer crosstalk: {np.round(m, 3).tolist()}')
    dc, layers, model, rms = _fit_and_eval(le, dc, 'negative')
    report.log(f'cdfs fit RMS (unmixed curves): {np.round(rms, 4).tolist()}')
    # print mid-grey: put log exposure 0 where the print itself (dyes + base) reflects /
    # transmits 18.4 % luminance under the viewing illuminant, so a mid-grey negative
    # exposure prints at the level of the shipped papers (they print about 0.46 sRGB)
    s = _visual_midgray_log_exposure(le, dc, cmy, base, recipe.viewing_illuminant)
    dc = shift_curves(le, dc, [-s] * 3)
    dc, layers, model, _ = _fit_and_eval(le, dc, 'negative')
    report.log(f'visual mid-grey anchor: log exposure shift {s:+.4f} '
               f'(layer density at 0: {np.round([np.interp(0.0, le, dc[:, i]) for i in range(3)], 3).tolist()})')

    info = ProfileInfo(
        stock=recipe.stock, name=recipe.name, type='negative', support=recipe.support or 'paper',
        stage='printing', use=recipe.use, antihalation=recipe.antihalation, target_print=None,
        channel_model='color', densitometer=densitometer_kind,
        log_sensitivity_density_over_min=float(recipe.log_sensitivity_density_over_min),
        reference_illuminant=recipe.reference_illuminant, viewing_illuminant=recipe.viewing_illuminant,
    )
    data = ProfileData(
        wavelengths=wl, log_sensitivity=ls,
        hanatos2025_adaptation_window_params=np.empty((0,)), hanatos2025_adaptation_surface_params=np.empty((0, 3)),
        channel_density=cmy, base_density=base, midscale_neutral_density=mid,
        log_exposure=le, density_curves=dc, density_curves_layers=layers, density_curves_model=model,
    )
    return Profile(metadata=_metadata(recipe), info=info, data=data)


def _metadata(recipe):
    metadata = ProfileMetadata()
    metadata.created = date.today().isoformat()
    metadata.copyright = recipe.copyright or (
        f'Copyright (c) {date.today().year} spektrafilm contributors; profile generated with '
        'spektrafilm_profile_builder from published data-sheet curves. Licensed under CC BY-SA 4.0.')
    metadata.datasource = (
        f'Generated with spektrafilm_profile_builder {__version__} from digitised data-sheet curves. '
        + (recipe.datasource.strip() + ' ' if recipe.datasource else '')
        + 'Original data are property of the respective holders.'
    )
    return metadata


def build_profile(record: RawRecord, recipe: Recipe, report: BuildReport | None = None) -> Profile:
    ptype = recipe.type
    if ptype == 'paper':
        return build_paper_profile(record, recipe, report)
    if ptype not in ('negative', 'positive'):
        raise ValueError(f'unsupported type {ptype!r}')
    report = report or BuildReport(recipe.stock, ptype)
    densitometer_kind = recipe.densitometer or ('status_A' if ptype == 'positive' else 'status_M')
    dstm = load_densitometer(densitometer_kind)
    wl = record.wavelengths

    # 1. spectral sensitivity, finite everywhere
    ls = extrapolate_log_sensitivity_tails(wl, record.log_sensitivity)

    # 2. characteristic curves: remove base+fog, put mid-grey at log exposure 0
    le, dc = _density_curves_on_grid(record)
    dc_min = measure_density_min(le, dc, ptype)
    dc = dc - dc_min
    dc, _ = _anchor(le, dc, ptype)
    report.log(f'base+fog (status {densitometer_kind[-1]}) RGB: {np.round(dc_min, 3).tolist()}')

    # 3. dye spectral densities
    if ptype == 'negative':
        if not record.has_mid_min:
            raise ValueError(f'{record.folder}: a negative needs dye_density_mid/min.csv')
        if record.has_cmy_dyes:
            cmy_start = record.dye_density_cmy
        else:
            cmy_start = load_generic_dyes(recipe.dye_start, wl)
        rec = reconstruct_dye_density(wl, record.dye_density_mid, record.dye_density_min, cmy_start, dstm)
        cmy = rec.dye_density
        base = record.dye_density_min.copy()
        mid = record.dye_density_mid.copy()
        report.log(f'dye reconstruction ({recipe.dye_start} start): cost {rec.cost:.4f}, '
                   f'dye peaks at mid-scale {np.round(rec.dye_peak_density, 3).tolist()}')
    else:
        if not record.has_cmy_dyes:
            raise ValueError(f'{record.folder}: a positive needs dye_density_c/m/y.csv')
        cmy = fill_dye_gaps(wl, record.dye_density_cmy)
        cmy = cmy / np.nanmax(cmy, axis=0)
        base = _positive_base_density(wl, dc_min)
        mid = None

    # 4. densitometer normalisation (unit status density per unit dye) and unmixing
    for _ in range(6):  # crosstalk is not linear in the dye amount: iterate to diag(M) = 1
        m = densitometer_crosstalk_matrix(dstm, cmy)
        cmy = cmy / np.diag(m)[None, :]
    m = densitometer_crosstalk_matrix(dstm, cmy)
    dc = np.einsum('ij,kj->ki', np.linalg.inv(m), dc)
    dc = np.where(np.isfinite(dc), np.clip(dc, 0, None), np.nan)
    report.log(f'densitometer crosstalk after normalisation: {np.round(m, 3).tolist()}')

    # 5. smooth model, then balance sensitivity for a neutral mid-grey
    dc, _, _, rms = _fit_and_eval(le, dc, ptype)
    report.log(f'cdfs fit RMS (unmixed curves): {np.round(rms, 4).tolist()}')
    ls, dc, corr = normalize_sensitivity(le, ls, dc, recipe.reference_illuminant)
    report.log(f'mid-grey raw exposure ratio G/RGB before normalisation: {np.round(corr, 4).tolist()}')
    dc, layers, model, _ = _fit_and_eval(le, dc, ptype)

    window, surface, donors = _hanatos_params(recipe.adaptation_donors, ptype, recipe.stock)
    report.log(f'hanatos2025 adaptation params averaged from: {donors}')

    profile = _assemble(recipe, densitometer_kind, wl, ls, cmy, base, mid, le, dc, layers, model,
                        window, surface)

    # 6. grey-ramp refinement through the runtime
    if recipe.grey_ramp_correction:
        filters = None
        if ptype == 'negative':
            filters, res = fit_neutral_print_filters(profile, recipe.target_print)
            filters = (filters[2], filters[1], filters[0])  # -> (Y, M, C)
        scale, shift, before, after = grey_ramp_correction(
            profile, recipe.target_print if ptype == 'negative' else None,
            positive=ptype == 'positive', data_trustability=recipe.data_trustability,
            filters_ymc=filters)
        report.log(f'grey ramp: density scale {np.round(scale, 4).tolist()}, '
                   f'log-exposure shift R/B {np.round(shift[[0, 2]], 4).tolist()}, '
                   f'ramp RMS {before:.4f} -> {after:.4f}')
        dc = scale_shift_curves(le, profile.data.density_curves, scale, shift)
        dc, _ = _anchor(le, dc, ptype)
        dc, layers, model, _ = _fit_and_eval(le, dc, ptype)
        profile.data.density_curves = dc
        profile.data.density_curves_layers = layers
        profile.data.density_curves_model = model
        if ptype == 'positive':
            # 7. exposure anchor: scanned mid-grey -> 18.4 %, as the shipped positives
            s = positive_scan_exposure_shift(profile)
            dc = scale_shift_curves(le, dc, (1, 1, 1), (s, s, s))
            dc, layers, model, _ = _fit_and_eval(le, dc, ptype)
            profile.data.density_curves = dc
            profile.data.density_curves_layers = layers
            profile.data.density_curves_model = model
            d0 = [np.interp(0.0, le, dc[:, i]) for i in range(3)]
            report.log(f'scan exposure anchor: shift {s:+.4f} log H, density at 0 EV {np.round(d0, 3).tolist()}')
    if ptype == 'positive':
        d0 = np.array([np.interp(0.0, le, dc[:, i]) for i in range(3)])
        profile.data.midscale_neutral_density = np.nan_to_num(cmy) @ d0 + base
    return profile


def _assemble(recipe, densitometer_kind, wl, ls, cmy, base, mid, le, dc, layers, model, window, surface):
    if mid is None:
        d0 = np.array([np.interp(0.0, le, dc[:, i]) for i in range(3)])
        mid = np.nan_to_num(cmy) @ d0 + base
    info = ProfileInfo(
        stock=recipe.stock, name=recipe.name, type=recipe.type, support='film', stage='filming',
        use=recipe.use, antihalation=recipe.antihalation, target_print=recipe.target_print,
        channel_model='color', densitometer=densitometer_kind,
        log_sensitivity_density_over_min=float(recipe.log_sensitivity_density_over_min),
        reference_illuminant=recipe.reference_illuminant, viewing_illuminant=recipe.viewing_illuminant,
    )
    data = ProfileData(
        wavelengths=wl, log_sensitivity=ls,
        hanatos2025_adaptation_window_params=window, hanatos2025_adaptation_surface_params=surface,
        channel_density=cmy, base_density=base, midscale_neutral_density=mid,
        log_exposure=le, density_curves=dc, density_curves_layers=layers, density_curves_model=model,
    )
    return Profile(metadata=_metadata(recipe), info=info, data=data)
