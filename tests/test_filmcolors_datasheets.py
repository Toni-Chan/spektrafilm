"""Profiles from data sheets catalogued by filmcolors.org: records, configs, estimates, overrides."""

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
       / 'filmcolors_data_sheets')
FILTERS = Path(__file__).resolve().parents[1] / 'src' / 'spektrafilm' / 'data' / 'filters' / 'neutral_print_filters.json'
CONFIGS = sorted((RAW / 'sheets').glob('*.json'))
RECORDS = list(csv.DictReader((RAW / 'records.csv').open()))
RECIPES = {r['stock']: r for r in csv.DictReader((RAW / 'recipes.csv').open())}
BUILT = sorted(RECIPES)
FILES = ('log_sensitivity_r', 'log_sensitivity_g', 'log_sensitivity_b', 'density_curve_r', 'density_curve_g',
         'density_curve_b')


def _xy(rec, name):
    return np.loadtxt(RAW / rec['folder'] / f'{name}.csv', delimiter=',', ndmin=2)


@pytest.mark.unit
def test_every_config_has_a_record_and_a_source_url():
    ids = {st['id'] for f in CONFIGS for st in json.loads(f.read_text())['stocks']}
    assert ids == {r['id'] for r in RECORDS}
    for f in CONFIGS:
        sheet = json.loads(f.read_text())
        assert sheet['url'].startswith('https://filmcolors.org/wp-content/uploads/')
        assert sheet['entry'].startswith('https://filmcolors.org/timeline-entry/')


@pytest.mark.unit
@pytest.mark.parametrize('rec', RECORDS, ids=[r['id'] for r in RECORDS])
def test_record_curves_are_complete_and_ordered(rec):
    folder = RAW / rec['folder']
    dyes = ('dye_density_c', 'dye_density_m', 'dye_density_y') if rec['type'] == 'positive' else ('dye_density_mid',)
    for name in FILES + dyes:
        xy = _xy(rec, name)
        assert len(xy) >= 15, name
        assert np.all(np.diff(xy[:, 0]) > 0), name
        assert np.all(np.isfinite(xy)), name
    info = (folder / 'info.txt').read_text()
    assert rec['url'] in info and 'filmcolors.org/timeline-entry' in info
    assert load_record(folder).guessed_type == rec['type']


@pytest.mark.unit
@pytest.mark.parametrize('rec', [r for r in RECORDS if r['type'] == 'positive'], ids=lambda r: r['id'])
def test_positive_curves_are_plausible(rec):
    for ch in 'rgb':
        d = _xy(rec, f'density_curve_{ch}')
        assert d[0, 1] > 2.0 and d[-1, 1] < 0.4  # reversal: dense at low exposure
        s = _xy(rec, f'log_sensitivity_{ch}')
        win = {'b': (380, 520), 'g': (470, 610), 'r': (560, 710)}
        if 'infrared' in rec['name'].lower():  # false-colour film: green-, red-, IR-sensitive layers, all blue-sensitive
            win = {'b': (380, 620), 'g': (380, 720), 'r': (380, 900)}
        lo, hi = win[ch]
        assert lo <= s[np.argmax(s[:, 1]), 0] <= hi
    for dye, (lo, hi) in {'y': (420, 470), 'm': (520, 570), 'c': (620, 690)}.items():
        xy = _xy(rec, f'dye_density_{dye}')
        assert lo <= xy[np.argmax(xy[:, 1]), 0] <= hi
        assert 0.85 <= xy[:, 1].max() <= 1.05  # normalised peaks (FUJIFILM) or dyes of a 1.0 neutral (KODAK)
        assert xy[:, 1].min() > -0.03


@pytest.mark.unit
@pytest.mark.parametrize('rec', [r for r in RECORDS if r['type'] == 'negative'], ids=lambda r: r['id'])
def test_negative_curves_are_plausible(rec):
    for ch in 'rgb':
        d = _xy(rec, f'density_curve_{ch}')
        assert d[0, 1] < 1.2 and d[-1, 1] - d[0, 1] > 1.2  # negative: D-min at low exposure, rising
        s = _xy(rec, f'log_sensitivity_{ch}')
        lo, hi = {'b': (380, 500), 'g': (500, 600), 'r': (590, 700)}[ch]
        assert lo <= s[np.argmax(s[:, 1]), 0] <= hi
    mid, dmin = _xy(rec, 'dye_density_mid'), _xy(rec, 'dye_density_min')
    w = np.linspace(max(mid[0, 0], dmin[0, 0]), min(mid[-1, 0], dmin[-1, 0]), 50)
    assert np.all(np.interp(w, *mid.T) > np.interp(w, *dmin.T))  # mid-scale above D-min everywhere
    assert dmin[:, 1].min() > 0.0


@pytest.mark.unit
def test_extraction_accuracy_is_recorded():
    summary = json.loads((RAW / 'extraction_summary.json').read_text())
    for rec in RECORDS:
        acc = summary[rec['id']]['accuracy']
        assert acc and max(a['p95_pt'] for a in acc.values()) < 1.0, rec['id']


@pytest.mark.unit
def test_record_only_sheets_are_not_built():
    for rec in RECORDS:
        assert rec['build'] in (rec['id'], 'record only'), rec['id']
        assert (rec['id'] in RECIPES) == (rec['build'] == rec['id']), rec['id']


@pytest.mark.parametrize('stock', BUILT)
def test_profiles_are_registered_finite_and_document_estimates(stock):
    assert stock in {s.value for s in FilmStocks}
    p = load_profile(stock)
    assert p.info.type == RECIPES[stock]['type']
    if p.info.type == 'positive':
        assert np.all(np.isfinite(p.data.channel_density))  # dye_extension hold_decay
    else:  # negatives: NaN outside 385-745 nm, as for the shipped data-sheet negatives
        w = np.asarray(p.data.wavelengths)
        assert np.all(np.isfinite(p.data.channel_density[(w >= 385) & (w <= 745)]))
    bd = np.asarray(p.data.base_density)
    assert np.all(bd[np.isfinite(bd)] >= 0)
    assert 'Estimate placeholders' in p.metadata.datasource
    assert 'filmcolors.org' in p.metadata.datasource
    if p.info.type == 'positive':
        assert p.info.densitometer == 'status_A'


def test_recipes_pin_donors_and_mark_estimates():
    for stock, r in RECIPES.items():
        assert r['adaptation_donors'].split()
        assert stock not in r['adaptation_donors'].split()
        assert 'Estimate placeholders' in r['datasource']
        if r['type'] == 'positive':
            assert r['dye_extension'] == 'hold_decay'
        else:
            assert r['target_print'] == 'fujifilm_crystal_archive_typeii'
    if 'fujifilm_t64_rtp_af3178e' in RECIPES:
        assert RECIPES['fujifilm_t64_rtp_af3178e']['reference_illuminant'] == 'T'


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
    cap = 1.8 if RECIPES[stock]['type'] == 'positive' else 2.0
    assert 1.0 < o['dir_couplers_interlayer_scale'] <= cap
