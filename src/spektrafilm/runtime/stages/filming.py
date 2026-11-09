from __future__ import annotations

from dataclasses import replace

import numpy as np

from spektrafilm.model.illuminants import standard_illuminant
from spektrafilm.model.color_filters import compute_band_pass_filter
from spektrafilm.model.diffusion import apply_diffusion_filter_um, apply_gaussian_blur_um, apply_halation_um, boost_highlights
from spektrafilm.model.develop import compute_density_spectral, develop, develop_simple
from spektrafilm.model.couplers import InhibitorExposure
from spektrafilm.profiles.extensions import load_profile_extension
from spektrafilm.utils.autoexposure import measure_autoexposure_ev
from spektrafilm.utils.spectral_upsampling import (
    compute_hanatos2025_tc_lut,
    rgb_to_raw_hanatos2025,
    rgb_to_raw_mallett2019,
)


def log_raw_from_raw(raw: np.ndarray) -> np.ndarray:
    return np.log10(np.fmax(raw, 0.0) + 1e-10)


class FilmingStage:
    def __init__(self, film, film_render_params, camera_params, io_params, settings_params,
                 lut_service, resize_service, enlarger_service, color_reference_service):
        self._film = film
        self._film_render = film_render_params
        self._camera = camera_params
        self._io = io_params
        self._settings = settings_params
        self._lut_service = lut_service
        self._resize_service = resize_service
        self._enlarger_service = enlarger_service
        
        # send info for hanatos2025 sensitivity adaptation to LUT service
        hanatos2025_adaptation = self._film.hanatos2025_adaptation()
        hanatos2025_adaptation.apply_window = self._settings.apply_hanatos2025_adaptation_window
        hanatos2025_adaptation.apply_surface = self._settings.apply_hanatos2025_adaptation_surface
        hanatos2025_adaptation.spectral_gaussian_blur = self._settings.spectral_gaussian_blur
        self._lut_service.set_hanatos2025_adaptation(hanatos2025_adaptation)
        self._hanatos2025_adaptation = hanatos2025_adaptation
        # Input gamut compression is per-bundle config (lives on params.io
        # so the GUI and bundle bakes share the same code path). The
        # service caches the LUT and invalidates it when this spec changes.
        self._lut_service.set_input_gamut_compress(self._io.input_gamut_compress)
        self._enlarger_service.density_spectral_midgray, self._enlarger_service.density_spectral_midgray_comp = self._compute_density_spectral_midgray_to_balance_print()
        self._color_reference_service = color_reference_service
        # Optional dye-less inhibitor layer (Fuji 4th colour layer), from the
        # profile-extension sidecar. None = feature off (no sidecar, or
        # disabled in params): the render is then bit-identical to builds
        # without this feature.
        self._inhibitor_layer = self._resolve_inhibitor_layer()
        self._inhibitor_cache = None
        self._pending_inhibitor_log_raw = None

    # public methods

    def auto_exposure(self, image: np.ndarray) -> float:
        if self._camera.auto_exposure:
            small_preview = self._resize_service.small_preview(image)
            autoexposure_ev = measure_autoexposure_ev(
                small_preview,
                self._io.input_color_space,
                self._io.input_cctf_decoding,
                method=self._camera.auto_exposure_method,
            )
            return image * 2 ** autoexposure_ev
        return image

    def expose(self, image: np.ndarray) -> np.ndarray:
        raw = self._rgb_to_film_raw(
            image,
            color_space=self._io.input_color_space,
            apply_cctf_decoding=self._io.input_cctf_decoding,
        )
        inhibitor_layer = getattr(self, '_inhibitor_layer', None)
        if inhibitor_layer is not None:
            raw_inhibitor = self._inhibitor_raw(image)
            reference_index = inhibitor_layer[0].reference_index
            raw_green_reference = raw[..., reference_index].copy()
        raw *= 2 ** self._camera.exposure_compensation_ev
        boost_highlights(raw, self._film_render.halation.boost_ev,
                         self._film_render.halation.boost_range,
                         self._film_render.halation.protect_ev, out=raw)
        raw = apply_diffusion_filter_um(
            raw,
            self._camera.diffusion_filter,
            pixel_size_um=self._resize_service.pixel_size_um,
        )
        raw = apply_gaussian_blur_um(raw, self._camera.lens_blur_um, self._resize_service.pixel_size_um)
        raw = apply_halation_um(raw, self._film_render.halation, self._resize_service.pixel_size_um)
        raw *= self._color_reference_service.black_white_filming_exposure_correction()
        if inhibitor_layer is not None:
            # The inhibitor layer follows its reference (green) layer through the
            # exposure-side operations (exposure compensation, highlight
            # boost, camera diffusion filter, lens blur, halation): its raw
            # is rescaled by the green layer's per-pixel gain. Exposure
            # scalings are reproduced exactly; spatial operations are
            # approximated by green's (the 4th layer sits next to the green
            # layer and peaks at ~500-520 nm). Exact in LUT mode.
            eps = 1e-6
            raw_inhibitor = raw_inhibitor * (np.fmax(raw[..., reference_index], 0.0) + eps) / (np.fmax(raw_green_reference, 0.0) + eps)
            self._pending_inhibitor_log_raw = np.log10(np.fmax(raw_inhibitor, 0.0) + 1e-10)
        return log_raw_from_raw(raw)

    def develop(self, log_raw: np.ndarray) -> np.ndarray:
        inhibitor = self._take_inhibitor_exposure(log_raw)
        return develop(
            log_raw,
            self._resize_service.pixel_size_um,
            self._film.data.log_exposure,
            self._film.data.density_curves,
            self._film.data.density_curves_layers,
            self._film_render.dir_couplers,
            self._film_render.grain,
            self._film.info.type,
            gamma_factor=self._film_render.density_curve_gamma,
            use_fast_stats=self._settings.use_fast_stats,
            inhibitor=inhibitor,
        )

    # private methods

    def _resolve_inhibitor_layer(self):
        couplers = self._film_render.dir_couplers
        if not getattr(couplers, 'cyan_inhibitor_active', False) or not couplers.active:
            return None
        stock = getattr(self._film.info, 'stock', None)
        extension = load_profile_extension(stock)
        if extension is None:
            return None
        layer = extension.inhibitor('cyan')
        if layer is None:
            return None
        amount = layer.amount_default * float(getattr(couplers, 'cyan_inhibitor_scale', 1.0))
        if amount <= 0:
            return None
        return layer, amount

    def _take_inhibitor_exposure(self, log_raw):
        """Inhibitor-layer exposure computed by the preceding ``expose`` call.

        Consumed once, so a run injected at the ``log_e_film`` tap (no
        spectral information) renders with the feature off instead of
        reusing a stale exposure.
        """
        pending = getattr(self, '_pending_inhibitor_log_raw', None)
        self._pending_inhibitor_log_raw = None
        inhibitor_layer = getattr(self, '_inhibitor_layer', None)
        if pending is None or inhibitor_layer is None:
            return None
        if pending.shape != np.shape(log_raw)[:2]:
            return None
        layer, amount = inhibitor_layer
        return InhibitorExposure(log_raw=pending, amount=amount, target=layer.target_index,
                                 reference=layer.reference_index)

    def _inhibitor_sensitivity(self) -> np.ndarray:
        layer, _ = self._inhibitor_layer
        wavelengths = np.asarray(self._film.data.wavelengths, dtype=float)
        log_sensitivity = np.asarray(layer.log_sensitivity, dtype=float)
        if layer.wavelengths.shape != wavelengths.shape or not np.allclose(layer.wavelengths, wavelengths):
            log_sensitivity = np.interp(wavelengths, layer.wavelengths, log_sensitivity, left=np.nan, right=np.nan)
        sensitivity = np.nan_to_num(10 ** log_sensitivity)[:, None]
        if self._camera.filter_uv[0] > 0 or self._camera.filter_ir[0] > 0:
            illuminant = standard_illuminant(self._film.info.reference_illuminant)
            band_pass_filter = compute_band_pass_filter(self._camera.filter_uv, self._camera.filter_ir)[:, None]
            normalization = np.sum(sensitivity * band_pass_filter * illuminant[:, None], axis=0) / np.sum(sensitivity * illuminant[:, None], axis=0)
            sensitivity = sensitivity * band_pass_filter / normalization
        # three identical columns so the 3-channel upsampling code paths apply unchanged
        return np.tile(sensitivity, (1, 3))

    def _inhibitor_raw_unscaled(self, rgb, sensitivity, tc_lut, color_space, apply_cctf_decoding):
        if self._settings.rgb_to_raw_method == "hanatos2025":
            raw = rgb_to_raw_hanatos2025(
                rgb, sensitivity,
                color_space=color_space,
                apply_cctf_decoding=apply_cctf_decoding,
                reference_illuminant=self._film.info.reference_illuminant,
                tc_lut=tc_lut,
            )
        elif self._settings.rgb_to_raw_method == "mallett2019":
            raw = rgb_to_raw_mallett2019(rgb, sensitivity,
                                         color_space=color_space,
                                         apply_cctf_decoding=apply_cctf_decoding,
                                         reference_illuminant=self._film.info.reference_illuminant)
        else:
            raise ValueError(f"Unsupported rgb_to_raw method: {self._settings.rgb_to_raw_method}")
        return np.asarray(raw)[..., 0]

    def _inhibitor_setup(self):
        """Sensitivity, tc LUT and grey normalisation of the inhibitor layer (cached).

        Same spectral integration as the image layers. The hanatos2025
        spectral window is applied, the per-channel exposure-correction
        surface is not (it is fitted for the R, G, B layers only). The
        result is scaled so that neutral grey gives the same raw exposure
        as the reference layer (green), so a neutral exposure of any level
        gives exactly zero departure from the data-sheet curves.
        """
        if self._inhibitor_cache is not None:
            return self._inhibitor_cache
        layer, _ = self._inhibitor_layer
        sensitivity = self._inhibitor_sensitivity()
        tc_lut = None
        if self._settings.rgb_to_raw_method == "hanatos2025":
            adaptation = self._hanatos2025_adaptation
            adaptation = replace(adaptation, apply_surface=False)
            tc_lut = compute_hanatos2025_tc_lut(
                sensitivity, adaptation, gamut_compress=self._io.input_gamut_compress,
            )
        grey = np.full((1, 1, 3), 0.184)
        color_space = self._io.input_color_space
        raw_grey_reference = float(np.asarray(self._rgb_to_film_raw(grey, color_space=color_space))[0, 0, layer.reference_index])
        raw_grey_inhibitor = float(self._inhibitor_raw_unscaled(grey, sensitivity, tc_lut, color_space, False)[0, 0])
        scale = raw_grey_reference / raw_grey_inhibitor if raw_grey_inhibitor > 0 else 0.0
        self._inhibitor_cache = (sensitivity, tc_lut, scale)
        return self._inhibitor_cache

    def _inhibitor_raw(self, image: np.ndarray) -> np.ndarray:
        sensitivity, tc_lut, scale = self._inhibitor_setup()
        raw = self._inhibitor_raw_unscaled(
            image, sensitivity, tc_lut, self._io.input_color_space, self._io.input_cctf_decoding,
        )
        return raw * scale

    def _rgb_to_film_raw(
        self,
        rgb: np.ndarray,
        *,
        color_space: str = "sRGB",
        apply_cctf_decoding: bool = False,
    ) -> np.ndarray:
        sensitivity = 10 ** self._film.data.log_sensitivity
        sensitivity = np.nan_to_num(sensitivity)

        if self._camera.filter_uv[0] > 0 or self._camera.filter_ir[0] > 0:
            illuminant = standard_illuminant(self._film.info.reference_illuminant)
            band_pass_filter = compute_band_pass_filter(self._camera.filter_uv, self._camera.filter_ir)
            band_pass_filter = np.tile(band_pass_filter[:, None], (1, 3))
            normalization = np.sum(sensitivity * band_pass_filter * illuminant[:, None], axis=0) / np.sum(sensitivity * illuminant[:, None], axis=0)
            sensitivity *= band_pass_filter / normalization

        if self._settings.rgb_to_raw_method == "hanatos2025":
            tc_lut = self._lut_service.get_filming_tc_lut(sensitivity)
            raw = rgb_to_raw_hanatos2025(
                rgb,
                sensitivity,
                color_space=color_space,
                apply_cctf_decoding=apply_cctf_decoding,
                reference_illuminant=self._film.info.reference_illuminant,
                tc_lut=tc_lut,
            )
        elif self._settings.rgb_to_raw_method == "mallett2019":
            raw = rgb_to_raw_mallett2019(rgb, sensitivity,
                            color_space=color_space,
                            apply_cctf_decoding=apply_cctf_decoding,
                            reference_illuminant=self._film.info.reference_illuminant)
        else:
            raise ValueError(f"Unsupported rgb_to_raw method: {self._settings.rgb_to_raw_method}")
        return raw
    
    def _compute_density_spectral_midgray_to_balance_print(self):
        rgb_midgray = np.array([[[0.184] * 3]])
        density_spectral_midgray = self._simple_rgb_to_density_spectral(rgb_midgray)
        if self._enlarger_service.print_exposure_compensation:
            neg_exp_comp_ev = self._camera.exposure_compensation_ev
            rgb_midgray_comp = np.array([[[0.184] * 3]]) * 2 ** neg_exp_comp_ev
            density_spectral_midgray_comp = self._simple_rgb_to_density_spectral(rgb_midgray_comp)
        else:
            density_spectral_midgray_comp = None
        return density_spectral_midgray, density_spectral_midgray_comp

    def _simple_rgb_to_density_spectral(self, rgb: np.ndarray) -> np.ndarray:
        raw = self._rgb_to_film_raw(rgb) 
        log_raw = np.log10(raw + 1e-10)
        density_cmy = develop_simple(
            log_raw,
            self._film.data.log_exposure,
            self._film.data.density_curves,
            gamma_factor=self._film_render.density_curve_gamma,
        )
        density_spectral = compute_density_spectral(
            self._film.data.channel_density,
            density_cmy,
            base_density=self._film.data.base_density,
        )
        return density_spectral
    