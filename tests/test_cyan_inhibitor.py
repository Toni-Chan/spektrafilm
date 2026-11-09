"""Fujifilm 4th colour layer (dye-less cyan-sensitive inhibitor layer)."""
from __future__ import annotations

import json

import colour
import numpy as np
import pytest

from spektrafilm.model.couplers import InhibitorExposure, apply_density_correction_dir_couplers
from spektrafilm.model.develop import develop
from spektrafilm.profiles.extensions import (
    list_profile_extensions, load_profile_extension, profile_extension_from_dict, profile_extension_to_dict,
)
from spektrafilm.profiles.io import list_profiles, load_profile
from spektrafilm.runtime.params_builder import digest_params, init_params
from spektrafilm.runtime.params_schema import DirCouplersParams, GrainParams
from spektrafilm.runtime.pipeline import SimulationPipeline

FDG = 'fujifilm_pro_400h_fdg'
KODAK = 'kodak_portra_400'


def _pipeline(stock, *, active=True, scale=1.0, lut=True, stochastic=False):
    p = init_params(film_profile=stock)
    p.debug.lut_mode = lut
    if not stochastic:
        p.debug.deactivate_stochastic_effects = True
    p.io.input_color_space = 'ProPhoto RGB'
    p.io.input_cctf_decoding = False
    p.film_render.dir_couplers.cyan_inhibitor_active = active
    p.film_render.dir_couplers.cyan_inhibitor_scale = scale
    return SimulationPipeline(digest_params(p))


def _colorchecker():
    cc = colour.CCS_COLOURCHECKERS['ColorChecker24 - After November 2014']
    xyy = np.array(list(cc.data.values()))
    rgb = colour.XYZ_to_RGB(colour.xyY_to_XYZ(xyy), 'ProPhoto RGB', illuminant=cc.illuminant,
                            chromatic_adaptation_transform='Bradford')
    return rgb.reshape(4, 6, 3)


def _de00(a, b):
    def lab(x):
        return colour.XYZ_to_Lab(colour.RGB_to_XYZ(np.clip(x, 0, None), 'sRGB', apply_cctf_decoding=True))
    return colour.delta_E(lab(a), lab(b), method='CIE 2000')


# --------------------------------------------------------------------- sidecar

@pytest.mark.unit
def test_sidecar_loads_on_profile_grid():
    ext = load_profile_extension(FDG)
    assert ext is not None and ext.stock == FDG
    layer = ext.inhibitor('cyan')
    profile = load_profile(FDG)
    np.testing.assert_allclose(layer.wavelengths, profile.data.wavelengths)
    assert layer.target == 'r' and layer.reference == 'g'
    assert layer.label == 'estimate'
    assert layer.amount_default > 0
    assert np.all(np.isfinite(layer.log_sensitivity))
    # peak of the 4th layer is in the blue-green
    assert 495 <= layer.wavelengths[np.argmax(layer.log_sensitivity)] <= 535


@pytest.mark.unit
def test_every_sidecar_matches_a_profile_and_profiles_stay_upstream_compatible():
    names = list_profile_extensions()
    assert len(names) == 15
    profiles = set(list_profiles())
    for name in names:
        assert name in profiles
        assert load_profile(name).info.type == 'negative'
    # sidecars are not profiles: nothing new in the profiles directory
    assert not any(n.startswith('profile_extension') for n in profiles)


@pytest.mark.unit
def test_sidecar_round_trip_and_validation():
    ext = load_profile_extension(FDG)
    again = profile_extension_from_dict(json.loads(json.dumps(profile_extension_to_dict(ext))))
    np.testing.assert_allclose(again.inhibitor().log_sensitivity, ext.inhibitor().log_sensitivity)
    assert again.inhibitor().amount_default == ext.inhibitor().amount_default
    bad = profile_extension_to_dict(ext)
    bad['inhibitor_layers'][0]['target'] = 'x'
    with pytest.raises(ValueError):
        profile_extension_from_dict(bad)
    bad = profile_extension_to_dict(ext)
    bad['inhibitor_layers'][0]['reference'] = 'r'
    with pytest.raises(ValueError):
        profile_extension_from_dict(bad)


@pytest.mark.unit
def test_no_sidecar_means_feature_off():
    assert load_profile_extension(KODAK) is None
    assert load_profile_extension(None) is None
    assert _pipeline(KODAK)._filming_stage._inhibitor_layer is None
    assert _pipeline(FDG)._filming_stage._inhibitor_layer is not None
    assert _pipeline(FDG, active=False)._filming_stage._inhibitor_layer is None
    assert _pipeline(FDG, scale=0.0)._filming_stage._inhibitor_layer is None


# ------------------------------------------------------------- bit identity

@pytest.mark.integration
@pytest.mark.parametrize('lut', [True, False])
def test_kodak_render_is_bit_identical(lut):
    img = _colorchecker()
    if not lut:
        img = np.repeat(np.repeat(img, 8, axis=0), 8, axis=1)
    on = _pipeline(KODAK, active=True, lut=lut).process(img)
    off = _pipeline(KODAK, active=False, lut=lut).process(img)
    assert np.array_equal(on, off)


@pytest.mark.integration
def test_fdg_amount_zero_is_bit_identical_to_off():
    img = _colorchecker()
    zero = _pipeline(FDG, scale=0.0).process(img)
    off = _pipeline(FDG, active=False).process(img)
    assert np.array_equal(zero, off)


@pytest.mark.unit
def test_develop_without_inhibitor_matches_zero_amount():
    rng = np.random.default_rng(0)
    log_raw = rng.uniform(-2.5, 1.0, (6, 5, 3))
    le = np.linspace(-4, 3, 200)
    curves = np.column_stack([np.clip(0.6 * (le + 2.5), 0, 2.4)] * 3)
    dc = DirCouplersParams(diffusion_size_um=0)
    args = (log_raw, None, le, curves, np.empty((0, 3, 3)), dc, GrainParams(active=False), 'negative')
    base = develop(*args, bypass_grain=True)
    zero = develop(*args, bypass_grain=True,
                   inhibitor=InhibitorExposure(log_raw=log_raw[..., 1] + 0.5, amount=0.0))
    assert np.array_equal(base, zero)


# ----------------------------------------------------------------- physics

@pytest.mark.integration
@pytest.mark.parametrize('lut', [True, False])
def test_neutral_ramp_is_preserved(lut):
    evs = np.arange(-3, 3.001, 0.5)
    ramp = (0.184 * 2.0 ** evs)[None, :, None] * np.ones((1, 1, 3))
    if not lut:
        ramp = np.repeat(np.repeat(ramp, 16, axis=0), 16, axis=1)
    on = _pipeline(FDG, lut=lut).process(ramp)
    off = _pipeline(FDG, active=False, lut=lut).process(ramp)
    assert _de00(on, off).max() < 0.5


@pytest.mark.unit
def test_neutral_exposure_gives_zero_correction():
    log_raw = np.tile(np.linspace(-3, 2, 11)[None, :, None], (2, 1, 3))
    le = np.linspace(-4, 3, 200)
    curves = np.column_stack([np.clip(0.6 * (le + 2.5), 0, 2.4)] * 3)
    density = np.zeros_like(log_raw)
    dc = DirCouplersParams(diffusion_size_um=0)
    inh = InhibitorExposure(log_raw=log_raw[..., 1].copy(), amount=1.0)
    with_inh = apply_density_correction_dir_couplers(density, log_raw, None, le, curves, dc, 'negative',
                                                     inhibitor=inh)
    without = apply_density_correction_dir_couplers(density, log_raw, None, le, curves, dc, 'negative')
    np.testing.assert_allclose(with_inh, without, atol=1e-12)


@pytest.mark.unit
def test_narrowband_500nm_reduces_red():
    from spektrafilm_profile_builder.extensions import model_effective_red_sensitivity
    from spektrafilm_profile_builder.spectral import WAVELENGTHS
    profile = load_profile(FDG)
    layer = load_profile_extension(FDG).inhibitor()
    off = model_effective_red_sensitivity(profile, layer.log_sensitivity, 0.0)
    on = model_effective_red_sensitivity(profile, layer.log_sensitivity, layer.amount_default)
    i = int(np.argmin(np.abs(WAVELENGTHS - 505)))
    assert on[i] < off[i] and on[i] < 0
    # long-wavelength red response is untouched
    j = int(np.argmin(np.abs(WAVELENGTHS - 640)))
    assert abs(on[j] - off[j]) < 0.02 * abs(off[j])
    # and the lobe reaches the CIE r-bar target the default amount was calibrated to
    vis = (WAVELENGTHS >= 400) & (WAVELENGTHS <= 700)
    assert on[i] / on[vis].max() < -0.2


@pytest.mark.integration
def test_pipeline_cyan_stimulus_lowers_red_density():
    # a blue-green colour (more cyan-layer than green exposure) loses red
    # density with the feature on; a yellow-green one gains it
    img = np.array([[[0.02, 0.25, 0.20], [0.20, 0.30, 0.02]]])  # ProPhoto linear
    on = _pipeline(FDG).process(img, collect='cmy_film')
    off = _pipeline(FDG, active=False).process(img, collect='cmy_film')
    assert on[0, 0, 0] < off[0, 0, 0]
    assert on[0, 1, 0] > off[0, 1, 0]


# ---------------------------------------------------------------- LUT mode

@pytest.mark.integration
def test_lut_mode_without_pixel_size():
    img = _colorchecker()
    on_pl = _pipeline(FDG)
    on = on_pl.process(img, inject='rgb_pre')
    off = _pipeline(FDG, active=False).process(img, inject='rgb_pre')
    assert on_pl._resize_service.pixel_size_um is None
    assert np.all(np.isfinite(on))
    assert not np.array_equal(on, off)


@pytest.mark.integration
def test_log_e_film_injection_falls_back_to_off():
    img = _colorchecker()
    on_pl = _pipeline(FDG)
    off_pl = _pipeline(FDG, active=False)
    log_e = off_pl.process(img, inject='rgb_pre', collect='log_e_film')
    on_pl.process(img, inject='rgb_pre', collect='log_e_film')  # leaves no stale state behind
    on_pl.process(img, inject='rgb_pre')
    a = on_pl.process(log_e, inject='log_e_film', collect='cmy_film')
    b = off_pl.process(log_e, inject='log_e_film', collect='cmy_film')
    assert np.array_equal(a, b)


# ----------------------------------------------------------------- builder

@pytest.mark.integration
def test_builder_reproduces_shipped_sidecar(tmp_path):
    from spektrafilm_profile_builder import cli
    recipes = ('src/spektrafilm_profile_builder/data/raw/fujifilm_professional_data_guide/recipes.csv')
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    profiles = root / 'src' / 'spektrafilm' / 'data' / 'profiles'
    assert cli.main(['extensions', str(root / recipes), '--profiles', str(profiles), '-o', str(tmp_path),
                     '--only', f'{FDG},fujifilm_velvia_50_fdg']) == 0
    written = sorted(p.name for p in tmp_path.iterdir())
    assert written == [f'{FDG}.json']     # reversal stocks have no cyan layer
    new = profile_extension_from_dict(json.loads((tmp_path / f'{FDG}.json').read_text()))
    shipped = load_profile_extension(FDG)
    np.testing.assert_allclose(new.inhibitor().log_sensitivity, shipped.inhibitor().log_sensitivity, atol=1e-4)
    assert new.inhibitor().amount_default == pytest.approx(shipped.inhibitor().amount_default, abs=2e-3)
