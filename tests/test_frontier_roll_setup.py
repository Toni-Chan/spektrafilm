import numpy as np
import pytest

from spektrafilm.model.frontier_roll_setup import RollDensitySetup
from spektrafilm.runtime.process import simulate, simulate_roll

from .conftest import make_fast_test_params

pytestmark = pytest.mark.unit


def _params(roll):
    p = make_fast_test_params()
    p.scanner.method = "frontier_sp500"
    p.scanner.frontier.roll_density_setup = roll
    return p


def _scene(scale=1.0):
    rng = np.random.default_rng(3)
    return [np.clip(rng.uniform(0.03, 0.7, (12, 12, 3)) * scale, 1e-4, None) for _ in range(3)]


def test_off_identity():
    frames = _scene()
    roll = simulate_roll(frames, _params("off"))
    for f, r in zip(frames, roll):
        np.testing.assert_allclose(r, simulate(f, _params("off")), atol=1e-7)


def test_fit_identity_on_matching_roll():
    d = np.random.default_rng(0).normal(1.0, 0.3, (50, 50, 3))
    setup = RollDensitySetup.fit([d], target_mid=np.median(d.reshape(-1, 3), axis=0), equalise_gains=False)
    np.testing.assert_allclose(setup.apply(d), d, atol=1e-12)


def test_bracket_convergence():
    """A whole roll shot one stop over or under converges to the normal roll after setup."""
    normal = simulate_roll(_scene(1.0), _params("roll"))
    over = simulate_roll(_scene(2.0), _params("roll"))
    under = simulate_roll(_scene(0.5), _params("roll"))
    raw_over = [simulate(f, _params("off")) for f in _scene(2.0)]
    raw_normal = [simulate(f, _params("off")) for f in _scene(1.0)]
    err_raw = np.mean([np.abs(a - b).mean() for a, b in zip(raw_over, raw_normal)])
    err_over = np.mean([np.abs(a - b).mean() for a, b in zip(over, normal)])
    err_under = np.mean([np.abs(a - b).mean() for a, b in zip(under, normal)])
    assert err_over < 0.25 * err_raw
    assert err_under < 0.05
