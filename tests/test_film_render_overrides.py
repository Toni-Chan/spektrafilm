"""Per-stock film rendering overrides (data/film_render_overrides/<stock>.json)."""
import copy
import importlib.resources as pkg_resources
import json

import colour
import numpy as np
import pytest

from spektrafilm.profiles.io import list_profiles, load_profile
from spektrafilm.runtime.api import simulate
import spektrafilm.runtime.params_builder as params_builder_module
from spektrafilm.runtime.params_builder import digest_params, init_params, load_film_render_overrides

_DIR = pkg_resources.files('spektrafilm.data').joinpath('film_render_overrides')
_FILES = sorted(p for p in _DIR.iterdir() if p.name.endswith('.json'))
_STOCKS = [p.name[:-5] for p in _FILES]


def _paper(stock):
    return 'kodak_portra_endura'


def test_override_directory_is_documented():
    assert _DIR.joinpath('README.md').is_file()


@pytest.mark.parametrize('stock', _STOCKS)
def test_override_file_is_valid_estimate(stock):
    data = json.loads(_DIR.joinpath(f'{stock}.json').read_text(encoding='utf-8'))
    assert data['stock'] == stock
    assert data['estimate'] is True
    assert data.get('note') and data.get('calibration')
    assert stock in list_profiles()
    scale = data['dir_couplers_interlayer_scale']
    assert 1.0 <= scale <= 2.0
    if load_profile(stock).info.type == 'positive':
        assert scale <= 1.8  # above ~2 the curve pre-correction crushes the blacks


def test_missing_override_is_empty():
    assert load_film_render_overrides('kodak_portra_400') == {}
    assert load_film_render_overrides('') == {}


@pytest.mark.parametrize('stock', _STOCKS)
def test_digest_scales_only_interlayer_gammas(stock, monkeypatch):
    scale = load_film_render_overrides(stock)['dir_couplers_interlayer_scale']
    base = digest_params(init_params(stock, _paper(stock)), apply_stocks_specifics=False)
    got = digest_params(init_params(stock, _paper(stock))).film_render.dir_couplers
    with monkeypatch.context() as m:
        m.setattr(params_builder_module, 'load_film_render_overrides', lambda _stock: {})
        ref = digest_params(init_params(stock, _paper(stock))).film_render.dir_couplers
    for name in ('gamma_interlayer_r_to_gb', 'gamma_interlayer_g_to_rb', 'gamma_interlayer_b_to_rg'):
        np.testing.assert_allclose(getattr(got, name), np.asarray(getattr(ref, name)) * scale)
    assert got.gamma_samelayer_rgb == ref.gamma_samelayer_rgb
    assert got.inhibition_interlayer == base.film_render.dir_couplers.inhibition_interlayer == 1.0
    # digesting twice must not compound the scale
    params = init_params(stock, _paper(stock))
    once = copy.deepcopy(digest_params(params).film_render.dir_couplers)
    twice = digest_params(params).film_render.dir_couplers
    assert once.gamma_interlayer_r_to_gb == twice.gamma_interlayer_r_to_gb


def _render(stock, image):
    params = init_params(stock, _paper(stock))
    params.debug.deactivate_stochastic_effects = True
    params.camera.auto_exposure = False
    params.io.scan_film = params.film.info.type == 'positive'
    params.io.input_color_space = 'sRGB'
    params.io.input_cctf_decoding = False
    params.io.output_color_space = 'sRGB'
    params.io.output_cctf_encoding = True
    return np.clip(np.asarray(simulate(np.ascontiguousarray(image), params)), 0, 1)


def _lab(srgb):
    return colour.XYZ_to_Lab(colour.sRGB_to_XYZ(srgb))


@pytest.mark.parametrize('stock', _STOCKS)
def test_override_keeps_grey_and_raises_chroma(stock, monkeypatch):
    def off(image):
        with monkeypatch.context() as m:
            m.setattr(params_builder_module, 'load_film_render_overrides', lambda _stock: {})
            return _render(stock, image)

    # 16 px patches: the DIR inhibitors diffuse spatially (~20 um)
    big = lambda a: np.repeat(np.repeat(a, 16, 0), 16, 1)
    grey = big(np.repeat(np.geomspace(0.01, 0.9, 12)[None, :, None], 3, axis=2))
    lab_on = _lab(_render(stock, grey))[8::16, 8::16]
    lab_off = _lab(off(grey))[8::16, 8::16]
    assert np.max(np.abs(lab_on[..., 1:] - lab_off[..., 1:])) < 2.5
    assert np.max(np.abs(lab_on[..., 0] - lab_off[..., 0])) < 3.0
    cc = colour.CCS_COLOURCHECKERS['ColorChecker24 - After November 2014']
    xyz = colour.xyY_to_XYZ(np.array(list(cc.data.values()))[:18])
    rgb = np.clip(colour.XYZ_to_sRGB(xyz, illuminant=cc.illuminant, apply_cctf_encoding=False), 0, None)
    patches = big(rgb.reshape(3, 6, 3))
    c_on = np.hypot(*_lab(_render(stock, patches))[8::16, 8::16, 1:].transpose(2, 0, 1)).mean()
    c_off = np.hypot(*_lab(off(patches))[8::16, 8::16, 1:].transpose(2, 0, 1)).mean()
    assert c_on > c_off + 2.0, (c_on, c_off)
