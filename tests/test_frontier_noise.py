import numpy as np
import pytest

from spektrafilm.model.frontier_optics import add_sensor_noise, quantise

pytestmark = pytest.mark.unit
SPEC = {"full_well_e": 20000.0, "read_noise_e": 15.0}


@pytest.mark.parametrize("signal", [0.01, 0.1, 0.5])
def test_noise_variance(signal):
    s = np.full((400, 400, 3), signal)
    out = add_sensor_noise(s, SPEC, np.random.default_rng(0))
    expected = (signal * SPEC["full_well_e"] + SPEC["read_noise_e"] ** 2) / SPEC["full_well_e"] ** 2
    assert abs(out.var() / expected - 1) < 0.02


def test_seed():
    s = np.full((8, 8, 3), 0.3)
    a = add_sensor_noise(s, SPEC, np.random.default_rng(42))
    b = add_sensor_noise(s, SPEC, np.random.default_rng(42))
    np.testing.assert_array_equal(a, b)
    assert not np.array_equal(a, add_sensor_noise(s, SPEC, np.random.default_rng(1)))


def test_noise_off_and_quantise():
    s = np.full((4, 4, 3), 0.3)
    assert add_sensor_noise(s, {"full_well_e": None, "read_noise_e": 0.0}, np.random.default_rng()) is s
    assert quantise(s, None) is s
    q = quantise(np.array([0.0, 0.5, 1.0, 1.2]), 2)
    np.testing.assert_allclose(q, [0, 2 / 3, 1, 1])
