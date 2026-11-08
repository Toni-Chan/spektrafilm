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


DEFAULT_CAPTURE_PRESET = "community_a"
DEFAULT_RENDER_PROFILE = "frontier_estimate"


class FrontierScanningStage:
    """Film CMY -> Frontier capture -> fixed positive rendering -> output RGB.

    Replaces both PrintingStage and ScanningStage for the Frontier methods.
    """

    def __init__(self, film, film_render_params, scanner_params, io_params, settings_params, lut_service,
                 resize_service=None, debug_params=None):
        from spektrafilm.model.frontier_render import StockReference, instrument_density
        from spektrafilm.model.scanner_profiles import load_capture_profile, load_render_profile

        self._film = film
        self._film_render = film_render_params
        self._scanner = scanner_params
        self._fr = scanner_params.frontier
        self._io = io_params
        self._settings = settings_params
        self._lut_service = lut_service
        self._resize_service = resize_service
        self._debug = debug_params
        self.timings = {}

        method = scanner_params.method
        if method not in ("frontier_sp3000", "frontier_sp500"):
            raise ValueError(f"FrontierScanningStage needs a frontier method, got {method!r}")
        self.capture_profile = load_capture_profile(
            scanner_params.capture_profile or f"{method}_{DEFAULT_CAPTURE_PRESET}")
        self.render_profile = load_render_profile(scanner_params.render_profile or DEFAULT_RENDER_PROFILE)


        dc = np.asarray(film.data.density_curves, dtype=np.float64)
        self._data_min = np.minimum(0.0, -np.asarray(film_render_params.grain.density_min, dtype=np.float64))
        self._data_max = np.nanmax(dc, axis=0) + 0.2
        self._capture_lut = None
        if settings_params.use_scanner_lut:
            self._capture_lut = lut_service.spectral_compute_frontier_capture(
                film, self.capture_profile, self._data_min, self._data_max)

        # film base in instrument density (CMY = 0)
        self.base_density = np.asarray(instrument_density(self._capture_direct(np.zeros((1, 3))))).reshape(3)

        # per-stock mid-grey anchor (fixed film-type setup, not per-roll)
        le = np.asarray(film.data.log_exposure, dtype=np.float64)
        probes = []
        for x in (-0.5, 0.0, 0.5):
            cmy = []
            for c in range(3):
                ok = np.isfinite(dc[:, c])
                cmy.append(np.interp(x, le[ok], dc[ok, c]))
            probes.append(cmy)
        d = np.asarray(instrument_density(self._capture_direct(np.asarray(probes)))) - self.base_density
        self.stock_reference = StockReference(d_mid=d[1], gamma=(d[2] - d[0]) / 1.0)
        if np.any(self.stock_reference.gamma <= 0):
            raise ValueError("film stock gives a non-positive instrument gamma; cannot render")

    def _capture_direct(self, cmy):
        return capture_direct(cmy, self._film, self.capture_profile)

    # pipeline nodes

    def _spatial_on(self) -> bool:
        return not (self._debug is not None and self._debug.deactivate_spatial_effects)

    def _stochastic_on(self) -> bool:
        return not (self._debug is not None and self._debug.deactivate_stochastic_effects)

    def _pixel_size_um(self):
        return None if self._resize_service is None else self._resize_service.pixel_size_um

    def capture(self, cmy_film: np.ndarray) -> InstrumentRGB:
        from spektrafilm.model.frontier_optics import add_sensor_noise, apply_flare, apply_mtf, quantise
        if self._capture_lut is not None:
            s = 10.0 ** self._capture_lut(cmy_film)
        else:
            s = self._capture_direct(cmy_film)
        cap = self.capture_profile
        if self._spatial_on() and np.ndim(s) == 3:
            s = apply_mtf(s, cap.mtf, self._pixel_size_um())
            s = apply_flare(s, cap.mtf.get("flare"), self._pixel_size_um())
        if self._stochastic_on():
            s = add_sensor_noise(s, cap.noise, np.random.default_rng(self._fr.seed))
        s = quantise(s, cap.adc_bits)
        return InstrumentRGB(s)

    def to_density(self, s: InstrumentRGB):
        from spektrafilm.model.frontier_render import instrument_density, remove_base
        return remove_base(instrument_density(s), self.base_density)

    def render(self, d) -> np.ndarray:
        from spektrafilm.model.frontier_render import (
            InstrumentDensity, apply_gradation, apply_user_offsets, tone_map,
        )
        if not isinstance(d, InstrumentDensity):
            d = InstrumentDensity(d, base_removed=True)  # tap contract: injected density is base-removed
        log_e = apply_gradation(d, self.render_profile, self._fr.contrast, self.stock_reference)
        log_e = apply_user_offsets(log_e, self._fr.density_offset, self._fr.brightness_offset)
        if self._fr.hyper_tone and self._spatial_on() and np.ndim(log_e) == 3:
            from spektrafilm.model.frontier_local_tone import hyper_tone
            log_e = hyper_tone(np.asarray(log_e), self._fr.hyper_tone)
        lin = np.asarray(tone_map(log_e, self.render_profile))
        if self._fr.sharpness != "off" and self._spatial_on() and lin.ndim == 3:
            from spektrafilm.model.frontier_local_tone import frontier_sharpen
            lin = frontier_sharpen(lin, self._fr.sharpness)
        return lin

    def output(self, rendered: np.ndarray) -> np.ndarray:
        from spektrafilm.model.frontier_render import to_output
        return np.asarray(to_output(rendered, self.render_profile, self._fr.output_space,
                                    cctf_encoding=self._io.output_cctf_encoding))

    def scan(self, cmy_film: np.ndarray) -> np.ndarray:
        return self.output(self.render(self.to_density(self.capture(cmy_film))))
