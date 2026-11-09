"""Tests for spektrafilm_profile_builder and the Fujifilm Professional Data
Guide profiles it produced (``*_fdg``)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from spektrafilm.model.stocks import FilmStocks, PrintPapers
from spektrafilm.profiles.io import list_profiles, load_profile, profile_from_dict
from spektrafilm.runtime.process import simulate
from spektrafilm.utils.io import read_neutral_print_filters

from spektrafilm_profile_builder import Recipe, build_profile, load_record
from spektrafilm_profile_builder.cli import main as cli_main, read_recipes
from spektrafilm_profile_builder.curves import evaluate_cdfs, fit_cdfs
from spektrafilm_profile_builder.process import _midgray_raw

from .conftest import make_fast_test_params

RAW = (Path(__file__).resolve().parents[1] / 'src' / 'spektrafilm_profile_builder' / 'data' / 'raw'
       / 'fujifilm_professional_data_guide')
RECIPES = RAW / 'recipes.csv'
FDG_STOCKS = [row['stock'] for row in csv.DictReader(RECIPES.open())]
PAPERS = [p.value for p in PrintPapers]
SHIPPED_ORIGINALS = {'fujifilm_pro_400h', 'fujifilm_provia_100f', 'fujifilm_velvia_100',
                     'fujifilm_xtra_400', 'fujifilm_c200'}

# Keys a downstream loader (e.g. SpektraLab's C++ profile.cpp) requires.
REQUIRED_INFO = ['stock', 'name', 'type', 'support', 'stage', 'use', 'antihalation', 'target_print',
                 'channel_model', 'densitometer', 'log_sensitivity_density_over_min',
                 'reference_illuminant', 'viewing_illuminant']
REQUIRED_DATA = ['wavelengths', 'log_sensitivity', 'hanatos2025_adaptation_window_params',
                 'hanatos2025_adaptation_surface_params', 'channel_density', 'base_density',
                 'midscale_neutral_density', 'log_exposure', 'density_curves', 'density_curves_layers',
                 'density_curves_model']


def _raw_json(stock):
    import importlib.resources as r
    return json.loads((r.files('spektrafilm.data.profiles') / f'{stock}.json').read_text())


def test_recipe_catalog_matches_shipped_profiles_and_enum():
    assert len(FDG_STOCKS) == 25
    shipped = set(list_profiles())
    enum_values = {s.value for s in FilmStocks}
    for stock in FDG_STOCKS:
        assert stock.endswith('_fdg')
        assert stock not in SHIPPED_ORIGINALS
        assert stock in shipped
        assert stock in enum_values


@pytest.mark.parametrize('stock', FDG_STOCKS)
def test_fdg_profile_loads_with_required_keys_and_shapes(stock):
    raw = _raw_json(stock)
    for key in REQUIRED_INFO:
        assert key in raw['info'], key
    for key in REQUIRED_DATA:
        assert key in raw['data'], key
    assert set(raw['metadata']) == {'version', 'copyright', 'created', 'license', 'citation', 'datasource'}
    assert 'Professional Data Guide' in raw['metadata']['datasource']

    p = load_profile(stock)  # runs spektrafilm's own validation
    info, d = p.info, p.data
    assert info.stock == stock
    assert info.name.endswith('(Pro Data Guide)')
    assert info.type in ('negative', 'positive')
    assert (info.support, info.stage, info.channel_model) == ('film', 'filming', 'color')
    assert info.log_sensitivity_density_over_min == 1.0
    assert info.densitometer == ('status_M' if info.type == 'negative' else 'status_A')
    if info.type == 'negative':
        assert info.target_print in PAPERS
    else:
        assert info.target_print is None

    assert d.wavelengths.shape == (81,)
    assert d.log_exposure.shape == (256,)
    assert d.log_sensitivity.shape == (81, 3) and np.all(np.isfinite(d.log_sensitivity))
    assert d.channel_density.shape == (81, 3)
    assert d.base_density.shape == (81,) and d.midscale_neutral_density.shape == (81,)
    assert d.density_curves.shape == (256, 3) and np.all(np.isfinite(d.density_curves))
    assert d.density_curves_layers.shape == (256, 3, 3)
    m = d.density_curves_model
    assert m.model_type == 'cdfs'
    assert m.centers.shape == m.amplitudes.shape == m.sigmas.shape == (3, 3)
    assert np.all(m.sigmas >= 0.05)
    curves, layers = evaluate_cdfs(d.log_exposure, m.centers, m.amplitudes, m.sigmas, info.type)
    np.testing.assert_allclose(curves, d.density_curves, atol=1e-9)
    np.testing.assert_allclose(layers, d.density_curves_layers, atol=1e-9)
    assert d.hanatos2025_adaptation_window_params.shape == (4,)
    assert d.hanatos2025_adaptation_surface_params.shape[0] == 3
    # sensitivities are normalised the way the runtime expects (mid-grey -> raw 1)
    np.testing.assert_allclose(_midgray_raw(d.log_sensitivity, info.reference_illuminant), 1.0, atol=2e-3)


def test_fdg_negatives_have_neutral_print_filters_on_every_paper():
    db = read_neutral_print_filters()
    for stock in FDG_STOCKS:
        if load_profile(stock).info.type != 'negative':
            continue
        for paper in PAPERS:
            cmy = db[paper]['TH-KG3'][stock]
            assert len(cmy) == 3 and all(np.isfinite(cmy))


@pytest.mark.integration
@pytest.mark.parametrize('stock', ['fujifilm_pro_400h_fdg', 'fujifilm_velvia_50_fdg'])
def test_fdg_profile_renders_through_default_pipeline(stock, small_rgb_image):
    p = load_profile(stock)
    params = make_fast_test_params(film_profile=stock, print_profile=p.info.target_print or 'kodak_portra_endura')
    params.io.scan_film = p.info.type == 'positive'
    out = simulate(small_rgb_image, params)
    assert out.shape == small_rgb_image.shape
    assert np.all(np.isfinite(out))


@pytest.mark.unit
def test_cdfs_fit_recovers_known_curve():
    le = np.linspace(-3, 4, 256)
    centers = np.array([[-1.0, 0.0, 1.0]] * 3)
    amps = np.array([[0.5, 0.6, 0.4]] * 3)
    sig = np.array([[0.4, 0.5, 0.6]] * 3)
    curves, _ = evaluate_cdfs(le, centers, amps, sig, 'negative')
    c, a, s, rms = fit_cdfs(le, curves, 'negative')
    assert np.all(rms < 1e-3)
    refit, _ = evaluate_cdfs(le, c, a, s, 'negative')
    np.testing.assert_allclose(refit, curves, atol=5e-3)


@pytest.mark.unit
def test_recipe_csv_points_at_existing_records():
    rows = read_recipes(RECIPES)
    assert len(rows) == 25
    for folder, recipe in rows:
        assert folder.is_dir()
        record = load_record(folder)
        assert record.guessed_type == recipe.type


@pytest.mark.parametrize('folder,ptype', [('positive/fujifilm_velvia_50', 'positive'),
                                          ('negative/fujifilm_superia_200', 'negative')])
def test_build_without_runtime_refinement_gives_valid_profile(folder, ptype):
    record = load_record(RAW / folder)
    recipe = Recipe(stock='test_stock', name='Test', type=ptype,
                    target_print='fujifilm_crystal_archive_typeii' if ptype == 'negative' else None,
                    grey_ramp_correction=False)
    profile = build_profile(record, recipe)
    from spektrafilm.profiles.io import _validate_profile
    _validate_profile(profile, 'test_stock')
    np.testing.assert_allclose(_midgray_raw(profile.data.log_sensitivity, 'D55'), 1.0, atol=2e-3)
    d0 = [np.interp(0.0, profile.data.log_exposure, profile.data.density_curves[:, i]) for i in range(3)]
    assert np.all(np.array(d0) > 0.3) and np.all(np.array(d0) < 1.2)


def test_cli_build_writes_loadable_json(tmp_path):
    rc = cli_main(['build', str(RAW / 'positive' / 'fujifilm_astia_100f'), '-o', str(tmp_path),
                   '--stock', 'my_astia', '--name', 'My Astia', '--no-grey-ramp'])
    assert rc == 0
    path = tmp_path / 'my_astia.json'
    payload = json.loads(path.read_text())
    profile = profile_from_dict(payload)
    assert profile.info.type == 'positive'
    assert profile.data.density_curves.shape == (256, 3)


@pytest.mark.parametrize('stock', FDG_STOCKS)
def test_fdg_profile_json_uses_only_upstream_schema_keys(stock):
    # Upstream's loader builds the dataclasses with **payload and rejects unknown keys,
    # so the profiles must not carry extra fields (e.g. Fuji's 4th cyan layer).
    from dataclasses import fields
    from spektrafilm.profiles.io import ProfileData, ProfileInfo, ProfileMetadata
    payload = _raw_json(stock)
    assert set(payload) == {'metadata', 'info', 'data'}
    assert set(payload['data']) <= {f.name for f in fields(ProfileData)}
    assert set(payload['info']) <= {f.name for f in fields(ProfileInfo)}
    assert set(payload['metadata']) <= {f.name for f in fields(ProfileMetadata)}


def test_fuji_cyan_inhibitor_layer_is_kept_raw_and_not_folded_into_red(tmp_path):
    import shutil
    src = RAW / 'negative' / 'fujifilm_superia_200'
    assert (src / 'log_sensitivity_cyan_layer.csv').is_file()
    stripped = tmp_path / 'fujifilm_superia_200'
    shutil.copytree(src, stripped)
    (stripped / 'log_sensitivity_cyan_layer.csv').unlink()
    recipe = Recipe(stock='test_stock', name='Test', type='negative',
                    target_print='fujifilm_crystal_archive_typeii', grey_ramp_correction=False)
    with_layer = build_profile(load_record(src), recipe)
    without_layer = build_profile(load_record(stripped), recipe)
    np.testing.assert_array_equal(with_layer.data.log_sensitivity, without_layer.data.log_sensitivity)



POSITIVE_FDG = [row['stock'] for row in csv.DictReader(RECIPES.open()) if row['type'] == 'positive']


@pytest.mark.unit
@pytest.mark.parametrize('stock', POSITIVE_FDG)
def test_fdg_positive_dye_nans_are_shared_by_all_channels(stock):
    # Reversal films are scanned through their own dyes and the runtime treats NaN
    # spectral density as opaque, so a NaN in one dye only (e.g. a yellow dye printed
    # only up to 600 nm) would black out that wavelength for every channel.
    nan = np.isnan(load_profile(stock).data.channel_density)
    assert np.array_equal(nan.any(axis=1), nan.all(axis=1))


@pytest.mark.integration
def test_fdg_positive_scans_midgray_like_shipped_positives():
    from spektrafilm_profile_builder.runtime_fit import render_midgray
    paper = load_profile('kodak_portra_endura')
    for stock in ['fujifilm_velvia_50_fdg', 'fujifilm_provia_100f_fdg', 'fujifilm_velvia_100']:
        out = render_midgray(load_profile(stock), paper, ev=0.0, scan_film=True)
        np.testing.assert_allclose(out, 0.184, atol=0.01)
