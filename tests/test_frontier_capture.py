import copy

import numpy as np
import pytest

from spektrafilm.model.film_spectral import film_spectral_density
from spektrafilm.model.scanner_profiles import (
    capture_profile_from_dict, grid_wavelengths, load_capture_profile,
)
from spektrafilm.runtime.params_builder import init_params
from spektrafilm.runtime.stages.frontier_scanning import (
    capture_crosstalk_matrix, capture_direct,
)

pytestmark = pytest.mark.unit
PV = {"label": "estimate", "source": "test"}


def _with_fwhm(fwhm):
    raw = copy.deepcopy(load_capture_profile("frontier_sp500_community_a").raw)
    for c in "RGB":
        raw["led_spd"][c]["gaussian"]["fwhm_nm"] = fwhm
    return capture_profile_from_dict(raw)


def test_delta_kernels_reproduce_transmittance_at_peak():
    film = init_params().film
    wl = grid_wavelengths()
    peaks = {"R": 630.0, "G": 550.0, "B": 460.0}
    raw = copy.deepcopy(load_capture_profile("frontier_sp500_community_a").raw)
    raw["effective_kernels"] = {
        c: {"wavelengths_nm": wl.tolist(), "values": (wl == p).astype(float).tolist(), "provenance": PV}
        for c, p in peaks.items()
    }
    cap = capture_profile_from_dict(raw)
    cmy = np.random.default_rng(1).uniform(0, 2.5, (6, 3))
    s = capture_direct(cmy, film, cap)
    d = film_spectral_density(cmy, film)
    for i, c in enumerate("RGB"):
        idx = int(np.where(wl == peaks[c])[0][0])
        np.testing.assert_allclose(s[:, i], 10 ** (-d[:, idx]), atol=1e-6)


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_narrow_kernels_have_less_crosstalk():
    film = init_params().film

    def offdiag(m):
        # rows R,G,B scanner channels; cols C,M,Y dyes; R<->C, G<->M, B<->Y
        return (m.sum() - np.trace(m)) / np.trace(m)

    assert offdiag(capture_crosstalk_matrix(film, _with_fwhm(10.0))) < \
        offdiag(capture_crosstalk_matrix(film, _with_fwhm(80.0)))


def test_capture_shapes_and_range():
    film = init_params().film
    cap = load_capture_profile("frontier_sp3000_community_b")
    s = capture_direct(np.zeros((2, 3, 3)), film, cap)
    assert s.shape == (2, 3, 3)
    assert np.all((s > 0) & (s <= 1))
    denser = capture_direct(np.ones((2, 3, 3)), film, cap)
    assert np.all(denser < s)


def test_capture_lut_matches_direct_and_caches():
    from spektrafilm.runtime.services import SpectralLUTService
    film = init_params().film
    cap = load_capture_profile("frontier_sp500_community_a")
    svc = SpectralLUTService(33)
    lo, hi = np.zeros(3), np.full(3, 3.0)
    f = svc.spectral_compute_frontier_capture(film, cap, lo, hi)
    cmy = np.random.default_rng(2).uniform(0.05, 2.9, (16, 16, 3))
    direct = np.log10(capture_direct(cmy, film, cap))
    err = np.max(np.abs(f(cmy) - direct))
    assert err < 1e-3, err
    assert svc.frontier_capture_lut_builds == 1
    svc.spectral_compute_frontier_capture(film, cap, lo, hi)
    assert svc.frontier_capture_lut_builds == 1
    svc.spectral_compute_frontier_capture(film, load_capture_profile("frontier_sp500_community_b"), lo, hi)
    assert svc.frontier_capture_lut_builds == 2
