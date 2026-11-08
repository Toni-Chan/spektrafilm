import numpy as np
import pytest

from spektrafilm.model.frontier_optics import apply_flare, apply_mtf, mtf_curve

pytestmark = pytest.mark.unit


def _mtf50_from_edge(img_row_stack, pixel_um):
    esf = img_row_stack.mean(axis=0)
    lsf = np.diff(esf)
    lsf = lsf * np.hanning(lsf.size)
    m = np.abs(np.fft.rfft(lsf))
    m /= m[0]
    f = np.fft.rfftfreq(lsf.size, d=pixel_um)
    i = np.argmax(m < 0.5)
    return np.interp(0.5, [m[i], m[i - 1]], [f[i], f[i - 1]])


@pytest.mark.parametrize("spec", [
    {"gaussians_um": [[6.0, 1.0]]},
    {"gaussians_um": [[4.0, 0.8], [15.0, 0.2]]},
])
def test_mtf50(spec):
    pixel_um = 1.0
    n = 512
    img = np.zeros((32, n, 3))
    img[:, n // 2:, :] = 1.0
    out = apply_mtf(img, spec, pixel_um)
    measured = _mtf50_from_edge(out[..., 1], pixel_um)
    f = np.linspace(0, 0.5, 20001)
    analytic = f[np.argmax(mtf_curve(spec, f) < 0.5)]
    assert abs(measured - analytic) / analytic < 0.05


def test_mtf_empty_is_identity_and_energy_conserved():
    img = np.random.default_rng(0).uniform(size=(16, 16, 3))
    assert apply_mtf(img, {"gaussians_um": []}, 5.0) is img
    out = apply_mtf(img, {"gaussians_um": [[5.0, 1.0]]}, 5.0)
    assert abs(out.mean() - img.mean()) < 1e-2


def test_flare_lifts_shadows_next_to_highlights():
    img = np.zeros((64, 64, 3))
    img[:, 32:] = 1.0
    out = apply_flare(img, {"fraction": 0.02, "sigma_um": 100.0}, 10.0)
    assert out[:, 28].mean() > 0
    assert apply_flare(img, {"fraction": 0.0, "sigma_um": 100.0}, 10.0) is img
