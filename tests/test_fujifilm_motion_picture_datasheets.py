"""Profiles from the FUJIFILM motion picture camera-negative data sheets (KB-series brochures and the
KB-1101E manual): records, configs, borrowed curves, estimates, overrides."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from spektrafilm.model.stocks import FilmStocks
from spektrafilm.profiles.io import load_profile
from spektrafilm.runtime.params_builder import load_film_render_overrides

from spektrafilm_profile_builder import load_record

RAW = (Path(__file__).resolve().parents[1] / 'src' / 'spektrafilm_profile_builder' / 'data' / 'raw'
       / 'fujifilm_motion_picture_data_sheets')
FILTERS = Path(__file__).resolve().parents[1] / 'src' / 'spektrafilm' / 'data' / 'filters' / 'neutral_print_filters.json'
CONFIGS = sorted((RAW / 'sheets').glob('*.json'))
STOCKS = {st['id']: st for f in CONFIGS for st in json.loads(f.read_text())['stocks']}
RECORDS = list(csv.DictReader((RAW / 'records.csv').open()))
RECIPES = {r['stock']: r for r in csv.DictReader((RAW / 'recipes.csv').open())}
BUILT = sorted(RECIPES)
FILES = ('log_sensitivity_r', 'log_sensitivity_g', 'log_sensitivity_b', 'density_curve_r', 'density_curve_g',
         'density_curve_b', 'dye_density_mid', 'dye_density_min')
TUNGSTEN = {'fujifilm_eterna_vivid_160_kb0701e', 'fujifilm_eterna_vivid_500_kb0901e', 'fujifilm_f250_kb914e',
            'fujifilm_f125_kb913e', 'fujifilm_eterna_250_kb1101e', 'fujifilm_eterna_400_kb1101e'}


def _xy(rec, name):
    return np.loadtxt(RAW / rec['folder'] / f'{name}.csv', delimiter=',', ndmin=2)


@pytest.mark.unit
def test_every_config_has_a_record_and_a_source_url():
    assert set(STOCKS) == {r['id'] for r in RECORDS}
    assert len(BUILT) == 9
    for f in CONFIGS:
        sheet = json.loads(f.read_text())
        assert sheet['url'].startswith('https://') and sheet['url'].endswith('.pdf')
        assert sheet['doc'].startswith('KB-')


@pytest.mark.unit
@pytest.mark.parametrize('rec', RECORDS, ids=[r['id'] for r in RECORDS])
def test_record_curves_are_complete_and_plausible(rec):
    for name in FILES:
        xy = _xy(rec, name)
        assert len(xy) >= 15, name
        assert np.all(np.diff(xy[:, 0]) > 0), name
        assert np.all(np.isfinite(xy)), name
    for ch in 'rgb':
        d = _xy(rec, f'density_curve_{ch}')
        assert d[0, 1] < 1.0 and d[-1, 1] - d[0, 1] > 0.9  # negative: D-min at low exposure, rising
        s = _xy(rec, f'log_sensitivity_{ch}')
        lo, hi = {'b': (380, 500), 'g': (500, 600), 'r': (590, 700)}[ch]
        assert lo <= s[np.argmax(s[:, 1]), 0] <= hi
    d = {ch: _xy(rec, f'density_curve_{ch}') for ch in 'rgb'}
    assert d['b'][0, 1] > d['g'][0, 1] > d['r'][0, 1]  # orange mask: status M D-min B > G > R
    mid, dmin = _xy(rec, 'dye_density_mid'), _xy(rec, 'dye_density_min')
    w = np.linspace(max(mid[0, 0], dmin[0, 0]), min(mid[-1, 0], dmin[-1, 0]), 50)
    assert np.all(np.interp(w, *mid.T) > np.interp(w, *dmin.T))
    info = (RAW / rec['folder'] / 'info.txt').read_text()
    assert rec['url'] in info
    assert load_record(RAW / rec['folder']).guessed_type == 'negative'


@pytest.mark.unit
@pytest.mark.parametrize('sid', sorted(s for s in STOCKS if STOCKS[s].get('borrow')))
def test_borrowed_curves_are_copies_and_documented(sid):
    b = STOCKS[sid]['borrow']
    rec = next(r for r in RECORDS if r['id'] == sid)
    src = next(r for r in RECORDS if r['id'] == b['from'])
    assert not STOCKS[b['from']].get('borrow')  # borrowed from a sheet with its own spectral plots
    for name in b['files']:
        assert (RAW / rec['folder'] / f'{name}.csv').read_text() == (RAW / src['folder'] / f'{name}.csv').read_text()
    info = (RAW / rec['folder'] / 'info.txt').read_text()
    assert 'Borrowed curves (estimate placeholders' in info and b['from'] in info
    summary = json.loads((RAW / 'extraction_summary.json').read_text())
    assert summary[sid]['borrowed']['source'] == b['from']
    assert b['from'] in RECIPES[sid]['datasource'] and float(RECIPES[sid]['data_trustability']) < 0.3


@pytest.mark.unit
def test_extraction_accuracy_is_recorded():
    summary = json.loads((RAW / 'extraction_summary.json').read_text())
    for rec in RECORDS:
        acc = summary[rec['id']]['accuracy']
        assert acc and max(a['p95_pt'] for a in acc.values()) < 1.0, rec['id']


@pytest.mark.parametrize('stock', BUILT)
def test_profiles_are_registered_cine_negatives_documenting_estimates(stock):
    assert stock in {s.value for s in FilmStocks}
    p = load_profile(stock)
    assert p.info.type == 'negative' and p.info.use == 'cine' and p.info.target_print == 'kodak_2383'
    assert p.info.reference_illuminant == ('T' if stock in TUNGSTEN else 'D55')
    assert p.info.log_sensitivity_density_over_min == pytest.approx(0.4)
    w = np.asarray(p.data.wavelengths)
    assert np.all(np.isfinite(p.data.channel_density[(w >= 400) & (w <= 700)]))
    bd = np.asarray(p.data.base_density)
    assert np.all(bd[np.isfinite(bd)] >= 0)
    assert 'Estimate placeholders' in p.metadata.datasource
    assert 'KB-' in p.metadata.datasource


def test_recipes_pin_donors_and_mark_estimates():
    for stock, r in RECIPES.items():
        assert r['adaptation_donors'].split() and stock not in r['adaptation_donors'].split()
        assert 'Estimate placeholders' in r['datasource'] and 'interlayer DIR' in r['datasource']
        assert r['use'] == 'cine'


def test_neutral_print_filters_cover_every_built_stock():
    db = json.loads(FILTERS.read_text())
    for paper, by_ill in db.items():
        for stock in BUILT:
            assert stock in by_ill['TH-KG3'], (paper, stock)


@pytest.mark.parametrize('stock', BUILT)
def test_interlayer_overrides_are_estimates_within_the_cap(stock):
    o = load_film_render_overrides(stock)
    if not o:
        return
    assert o['estimate'] is True and o['stock'] == stock
    assert 1.0 < o['dir_couplers_interlayer_scale'] <= 2.0
