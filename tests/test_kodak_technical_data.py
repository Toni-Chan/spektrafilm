"""Profiles built from the KODAK technical data sheets (E-series, 1997-2003),
``kodak_<stock>_<pubcode>``: catalogue, schema, shapes, filters, rendering."""

from __future__ import annotations

import csv
import json
from dataclasses import fields
from pathlib import Path

import numpy as np
import pytest

from spektrafilm.model.stocks import FilmStocks, PrintPapers
from spektrafilm.profiles.io import ProfileData, ProfileInfo, ProfileMetadata, list_profiles, load_profile
from spektrafilm.runtime.process import simulate
from spektrafilm.utils.io import read_neutral_print_filters

from spektrafilm_profile_builder import Recipe, build_profile, load_record
from spektrafilm_profile_builder.cli import read_recipes
from spektrafilm_profile_builder.curves import evaluate_cdfs
from spektrafilm_profile_builder.process import _midgray_raw

from .conftest import make_fast_test_params

RAW = (Path(__file__).resolve().parents[1] / 'src' / 'spektrafilm_profile_builder' / 'data' / 'raw'
       / 'kodak_technical_data')
RECIPES = RAW / 'recipes.csv'
ROWS = list(csv.DictReader(RECIPES.open()))
STOCKS = [r['stock'] for r in ROWS]
FILMS = [r['stock'] for r in ROWS if r['type'] != 'paper']
NEGATIVES = [r['stock'] for r in ROWS if r['type'] == 'negative']
POSITIVES = [r['stock'] for r in ROWS if r['type'] == 'positive']
PAPERS_NEW = [r['stock'] for r in ROWS if r['type'] == 'paper']
PAPERS = [p.value for p in PrintPapers]
# profiles shipped before this data set, which must stay untouched
SHIPPED_KODAK = {'kodak_2383', 'kodak_2393', 'kodak_ektachrome_100', 'kodak_ektacolor_edge', 'kodak_ektar_100',
                 'kodak_endura_premier', 'kodak_gold_200', 'kodak_kodachrome_64', 'kodak_portra_160',
                 'kodak_portra_400', 'kodak_portra_800', 'kodak_portra_800_push1', 'kodak_portra_800_push2',
                 'kodak_portra_endura', 'kodak_supra_endura', 'kodak_ultra_endura', 'kodak_ultramax_400',
                 'kodak_verita_200d', 'kodak_vision3_200t', 'kodak_vision3_250d', 'kodak_vision3_500t',
                 'kodak_vision3_50d'}


def _raw_json(stock):
    import importlib.resources as r
    return json.loads((r.files('spektrafilm.data.profiles') / f'{stock}.json').read_text())


def test_catalogue_lists_all_69_sheets():
    rows = list(csv.DictReader((RAW / 'index.csv').open()))
    assert len(rows) == 69
    assert {r['file'] for r in rows} >= {'e190-1.pdf', 'e190.pdf', 'e4021.pdf', 'e8.pdf'}
    assert all(r['publication'].startswith('E-') for r in rows)


def test_recipes_are_registered_and_do_not_collide():
    shipped = set(list_profiles())
    films = {s.value for s in FilmStocks}
    papers = set(PAPERS)
    assert len(STOCKS) == len(set(STOCKS))
    for r in ROWS:
        stock = r['stock']
        assert stock.startswith('kodak_') and stock not in SHIPPED_KODAK
        assert stock in shipped
        assert stock in (papers if r['type'] == 'paper' else films)


@pytest.mark.unit
def test_recipe_csv_points_at_existing_records():
    rows = read_recipes(RECIPES)
    assert len(rows) == len(ROWS)
    for folder, recipe in rows:
        assert folder.is_dir()
        assert load_record(folder).guessed_type == recipe.type


@pytest.mark.parametrize('stock', STOCKS)
def test_profile_json_uses_only_upstream_schema_keys(stock):
    payload = _raw_json(stock)
    assert set(payload) == {'metadata', 'info', 'data'}
    assert set(payload['data']) <= {f.name for f in fields(ProfileData)}
    assert set(payload['info']) <= {f.name for f in fields(ProfileInfo)}
    assert set(payload['metadata']) <= {f.name for f in fields(ProfileMetadata)}
    assert 'KODAK technical data E-' in payload['metadata']['datasource']


@pytest.mark.parametrize('stock', STOCKS)
def test_profile_loads_with_expected_info_and_shapes(stock):
    row = ROWS[STOCKS.index(stock)]
    p = load_profile(stock)  # spektrafilm's own validation
    info, d = p.info, p.data
    assert info.stock == stock
    assert '(E-' in info.name and info.name.startswith('Kodak')
    assert info.channel_model == 'color'
    assert d.wavelengths.shape == (81,)
    assert d.log_exposure.shape == (256,)
    assert d.log_sensitivity.shape == (81, 3) and np.all(np.isfinite(d.log_sensitivity))
    assert d.channel_density.shape == (81, 3)
    assert d.base_density.shape == (81,) and d.midscale_neutral_density.shape == (81,)
    assert d.density_curves.shape == (256, 3) and np.all(np.isfinite(d.density_curves))
    assert d.density_curves_layers.shape == (256, 3, 3)
    if row['type'] != 'negative':
        # scanned / viewed materials: NaN density is opaque, so it must be shared by all dyes
        # (negatives keep the printed range per dye, like the shipped negatives)
        nan = np.isnan(d.channel_density)
        assert np.array_equal(nan.any(axis=1), nan.all(axis=1))
        assert np.all(np.isfinite(d.base_density))
    m = d.density_curves_model
    assert m.model_type == 'cdfs' and m.centers.shape == (3, 3)
    curves, _ = evaluate_cdfs(d.log_exposure, m.centers, m.amplitudes, m.sigmas,
                              'positive' if info.type == 'positive' else 'negative')
    np.testing.assert_allclose(curves, d.density_curves, atol=1e-9)
    if row['type'] == 'paper':
        assert (info.type, info.stage, info.densitometer) == ('negative', 'printing', 'status_A')
        assert info.support == (row['support'] or 'paper')
        assert info.reference_illuminant == 'TH-KG3' and info.target_print is None
        assert d.hanatos2025_adaptation_window_params.size == 0
        # log exposure 0 = green at D 0.735 over D-min (upstream paper convention)
        d0 = np.interp(0.0, d.log_exposure, d.density_curves[:, 1])
        assert 0.2 < d0 < 1.2
    else:
        assert (info.support, info.stage) == ('film', 'filming')
        assert info.type == row['type']
        assert info.densitometer == ('status_M' if info.type == 'negative' else 'status_A')
        assert info.target_print == ('kodak_portra_endura' if info.type == 'negative' else None)
        assert info.log_sensitivity_density_over_min == float(row['log_sensitivity_density_over_min'])
        np.testing.assert_allclose(_midgray_raw(d.log_sensitivity, info.reference_illuminant), 1.0, atol=2e-3)


def test_every_film_has_filters_on_every_paper():
    db = read_neutral_print_filters()
    films = [s.value for s in FilmStocks]
    for paper in PAPERS:
        for stock in films:
            cmy = db[paper]['TH-KG3'][stock]
            assert len(cmy) == 3 and all(np.isfinite(cmy)), (paper, stock)


@pytest.mark.integration
@pytest.mark.parametrize('stock', ['kodak_portra_160nc_e190', 'kodak_ektachrome_e100vs_e163'])
def test_film_renders_through_default_pipeline(stock, small_rgb_image):
    p = load_profile(stock)
    params = make_fast_test_params(film_profile=stock, print_profile=p.info.target_print or 'kodak_portra_endura')
    params.io.scan_film = p.info.type == 'positive'
    out = simulate(small_rgb_image, params)
    assert out.shape == small_rgb_image.shape and np.all(np.isfinite(out))


@pytest.mark.integration
@pytest.mark.parametrize('paper', ['kodak_portra_endura_e4021', 'kodak_duratrans_e143'])
def test_paper_prints_portra_400_midgray_neutral(paper):
    from spektrafilm_profile_builder.runtime_fit import fit_neutral_print_filters, render_midgray
    film = load_profile('kodak_portra_400')
    cmy, res = fit_neutral_print_filters(film, paper)
    assert res < 1e-3
    db = read_neutral_print_filters()
    np.testing.assert_allclose(db[paper]['TH-KG3']['kodak_portra_400'], cmy, atol=0.5)


@pytest.mark.unit
def test_paper_build_without_runtime_gives_valid_profile():
    from spektrafilm.profiles.io import _validate_profile
    record = load_record(RAW / 'paper' / 'kodak_portra_endura_e4021')
    profile = build_profile(record, Recipe(stock='test_paper', name='Test', type='paper',
                                           reference_illuminant='TH-KG3', viewing_illuminant='D50'))
    _validate_profile(profile, 'test_paper')
    assert profile.info.support == 'paper' and profile.info.stage == 'printing'
