"""KODACHROME 25 / 64 / 200 from KODAK E-55 (June 2009): records, estimate placeholders, overrides."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest

from spektrafilm.profiles.io import load_profile
from spektrafilm.runtime.params_builder import load_film_render_overrides

from spektrafilm_profile_builder import load_record
from spektrafilm_profile_builder.spectral import WAVELENGTHS, extend_dyes_beyond_sheet, fill_dye_gaps

RAW = (Path(__file__).resolve().parents[1] / 'src' / 'spektrafilm_profile_builder' / 'data' / 'raw'
       / 'kodak_technical_data')
E55 = ['kodak_kodachrome_25_e55', 'kodak_kodachrome_64_e55', 'kodak_kodachrome_200_e55']


def _xy(stock, name):
    return np.loadtxt(RAW / 'positive' / stock / f'{name}.csv', delimiter=',', ndmin=2)


@pytest.mark.unit
@pytest.mark.parametrize('stock', E55)
def test_record_has_all_e55_curve_sets(stock):
    folder = RAW / 'positive' / stock
    for n in ('log_sensitivity_r', 'log_sensitivity_g', 'log_sensitivity_b', 'density_curve_r', 'density_curve_g',
              'density_curve_b', 'dye_density_c', 'dye_density_m', 'dye_density_y', 'dye_density_neutral', 'mtf'):
        assert (folder / f'{n}.csv').is_file(), n
    info = (folder / 'info.txt').read_text()
    assert 'E-55' in info and 'https://125px.com/docs/film/kodak/e55.pdf' in info
    assert 'K-14' in info
    assert load_record(folder).guessed_type == 'positive'


@pytest.mark.unit
@pytest.mark.parametrize('stock', E55)
def test_dyes_read_above_the_top_label(stock):
    # E-55 draws cyan and the visual neutral above the 1.0 label (peaks ~1.2-1.4)
    assert _xy(stock, 'dye_density_c')[:, 1].max() > 1.1
    assert _xy(stock, 'dye_density_neutral')[:, 1].max() > 1.2
    assert 630 < _xy(stock, 'dye_density_c')[np.argmax(_xy(stock, 'dye_density_c')[:, 1]), 0] < 655


@pytest.mark.unit
def test_k25_mean_wavelengths_match_visns_e77_analysis():
    # area-normalised linear sensitivity over the printed range; visns.neocities.org (from E-77, 1980):
    # 444.3 / 554.8 / 632.0 nm
    ref = {'b': 444.3, 'g': 554.8, 'r': 632.0}
    for ch, want in ref.items():
        xy = _xy('kodak_kodachrome_25_e55', f'log_sensitivity_{ch}')
        g = np.arange(np.ceil(xy[0, 0]), np.floor(xy[-1, 0]) + 0.01, 0.5)
        s = 10 ** np.interp(g, xy[:, 0], xy[:, 1])
        assert abs((g * s).sum() / s.sum() - want) < 5.0, ch


@pytest.mark.unit
def test_dye_extension_is_finite_and_keeps_printed_values():
    rng = np.full((WAVELENGTHS.size, 3), np.nan)
    sel = (WAVELENGTHS >= 420) & (WAVELENGTHS <= 700)
    rng[sel] = [0.5, 0.3, 0.1]
    out = extend_dyes_beyond_sheet(WAVELENGTHS, rng)
    assert np.all(np.isfinite(out))
    np.testing.assert_allclose(out[sel], fill_dye_gaps(WAVELENGTHS, rng)[sel])
    np.testing.assert_allclose(out[WAVELENGTHS < 420], [[0.5, 0.3, 0.1]] * int((WAVELENGTHS < 420).sum()))
    assert np.all(np.diff(out[WAVELENGTHS >= 700, 0]) < 0)


@pytest.mark.parametrize('stock', E55)
def test_profiles_are_finite_with_estimates_documented(stock):
    p = load_profile(stock)
    assert np.all(np.isfinite(p.data.channel_density))  # dye_extension hold_decay
    assert np.all(p.data.base_density >= 0)
    assert 'Estimate placeholders' in p.metadata.datasource
    assert 'https://125px.com/docs/film/kodak/e55.pdf' in p.metadata.datasource
    assert p.info.type == 'positive' and p.info.densitometer == 'status_A'


def test_recipes_mark_e55_estimates():
    rows = {r['stock']: r for r in csv.DictReader((RAW / 'recipes.csv').open())}
    for stock in E55:
        assert rows[stock]['dye_extension'] == 'hold_decay'
        assert rows[stock]['adaptation_donors']
    assert rows['kodak_kodachrome_25_e55']['density_min'] == '0.10;0.10;0.10'


@pytest.mark.parametrize('stock', E55)
def test_interlayer_override_is_an_estimate_within_the_positive_cap(stock):
    o = load_film_render_overrides(stock)
    assert o['estimate'] is True and o['stock'] == stock
    assert 1.0 < o['dir_couplers_interlayer_scale'] <= 1.8
