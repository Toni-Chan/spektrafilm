import numpy as np
import pytest

from spektrafilm.model.develop import compute_density_spectral
from spektrafilm.model.film_spectral import film_spectral_density
from spektrafilm.runtime.params_builder import init_params

pytestmark = pytest.mark.unit


def test_matches_scanning_stage_formula():
    film = init_params().film
    cmy = np.random.default_rng(0).uniform(0, 2, (4, 5, 3))
    ref = compute_density_spectral(film.data.channel_density, cmy, film.data.base_density)
    np.testing.assert_array_equal(film_spectral_density(cmy, film), ref)


def test_zero_cmy_gives_base():
    film = init_params().film
    d = film_spectral_density(np.zeros(3), film)
    np.testing.assert_allclose(d, film.data.base_density)
    assert np.all(np.nan_to_num(film_spectral_density(np.zeros(3), film, include_base=False)) == 0)
