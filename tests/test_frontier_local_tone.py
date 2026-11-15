import numpy as np
import pytest

import spektrafilm.model.frontier_local_tone as lt
from spektrafilm.runtime.params_builder import digest_params
from spektrafilm.runtime.pipeline import SimulationPipeline

from .conftest import make_fast_test_params

pytestmark = pytest.mark.unit


def _img():
    x = np.linspace(-1.5, 1.5, 64)
    img = np.ones((64, 64, 3)) * x[None, :, None]
    img[20:24, 20:24] += 0.3  # local detail
    return img


def test_defaults_noop():
    img = _img()
    assert lt.hyper_tone(img, 0.0) is img
    assert lt.frontier_sharpen(img, "off") is img


def test_hyper_tone_compresses_range_keeps_detail():
    img = _img()
    out = lt.hyper_tone(img, 0.6)
    assert np.ptp(out) < np.ptp(img)
    detail_in = img[22, 22, 0] - img[22, 26, 0]
    detail_out = out[22, 22, 0] - out[22, 26, 0]
    assert detail_out > 0.5 * detail_in


def test_sharpen_once(monkeypatch):
    calls = []
    real = lt.apply_unsharp_mask

    def counting(*a, **k):
        calls.append(1)
        return real(*a, **k)

    import spektrafilm.model.diffusion as diffusion
    monkeypatch.setattr(lt, "apply_unsharp_mask", counting)
    import spektrafilm.runtime.stages.scanning as scanning
    monkeypatch.setattr(diffusion, "apply_unsharp_mask", counting)
    monkeypatch.setattr(scanning, "apply_unsharp_mask", counting)
    p = make_fast_test_params()
    p.debug.deactivate_spatial_effects = False
    p.scanner.method = "frontier_sp500"
    p.scanner.frontier.sharpness = "std"
    p.scanner.unsharp_mask = (0.7, 0.7)
    p = digest_params(p)
    p.debug.deactivate_spatial_effects = False
    pipe = SimulationPipeline(p)
    pipe.process(np.random.default_rng(0).uniform(0.05, 0.8, (16, 16, 3)))
    assert len(calls) == 1
