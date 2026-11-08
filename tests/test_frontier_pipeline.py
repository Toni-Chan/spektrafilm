import numpy as np
import pytest

from spektrafilm.runtime.params_builder import digest_params
from spektrafilm.runtime.pipeline import SimulationPipeline
from spektrafilm.runtime.process import simulate
from spektrafilm.runtime.topology import Tap

from .conftest import make_fast_test_params

pytestmark = pytest.mark.integration


def _frontier_params(method="frontier_sp500", **fr):
    p = make_fast_test_params()
    p.scanner.method = method
    for k, v in fr.items():
        setattr(p.scanner.frontier, k, v)
    return digest_params(p)


def _gray_ramp():
    ramp = np.geomspace(0.01, 1.0, 16)
    return np.ones((4, 16, 3)) * ramp[None, :, None]


@pytest.mark.parametrize("method", ["frontier_sp500", "frontier_sp3000"])
def test_frontier_end_to_end(method):
    out = simulate(_gray_ramp(), _frontier_params(method), digest_params_first=False)
    assert out.shape == (4, 16, 3)
    assert np.all(np.isfinite(out)) and out.min() >= 0 and out.max() <= 1
    # brighter scene -> brighter positive
    assert np.all(np.diff(out[0].mean(axis=1)) > 0)


def test_frontier_mid_grey_is_near_neutral():
    img = np.full((4, 4, 3), 0.184)
    out = simulate(img, _frontier_params(), digest_params_first=False)
    rgb = out[0, 0]
    assert np.ptp(rgb) < 0.05, rgb


def test_frontier_bypasses_printing():
    pipe = SimulationPipeline(_frontier_params())
    labels = [n.label for n in pipe._topology]
    assert not any(l.startswith("printing") or l.startswith("scanning") for l in labels)
    assert "frontier.capture" in labels


@pytest.mark.parametrize("tap", [Tap.INSTRUMENT_RGB, Tap.INSTRUMENT_DENSITY, Tap.FRONTIER_RENDERED])
def test_frontier_debug_taps(tap):
    pipe = SimulationPipeline(_frontier_params())
    out = pipe.process(_gray_ramp(), collect=tap)
    assert out.shape == (4, 16, 3) and np.all(np.isfinite(out))


def test_frontier_inject_density():
    pipe = SimulationPipeline(_frontier_params())
    d = pipe.process(_gray_ramp(), collect=Tap.INSTRUMENT_DENSITY)
    full = pipe.process(_gray_ramp())
    np.testing.assert_allclose(pipe.process(np.asarray(d), inject=Tap.INSTRUMENT_DENSITY), full)


def test_frontier_lut_path_close_to_direct():
    p = _frontier_params()
    direct = simulate(_gray_ramp(), p, digest_params_first=False)
    p.settings.use_scanner_lut = True
    lut = simulate(_gray_ramp(), p, digest_params_first=False)
    assert np.max(np.abs(lut - direct)) < 5e-3


def test_frontier_offsets_change_output():
    base = simulate(_gray_ramp(), _frontier_params(), digest_params_first=False)
    brighter = simulate(_gray_ramp(), _frontier_params(brightness_offset=1.0), digest_params_first=False)
    assert brighter.mean() > base.mean()
    less_red = simulate(_gray_ramp(), _frontier_params(density_offset=(0.2, 0.0, 0.0)), digest_params_first=False)
    assert less_red[..., 0].mean() < base[..., 0].mean()


def test_default_method_topology_unchanged():
    pipe = SimulationPipeline(make_fast_test_params())
    assert pipe._frontier_stage is None
    assert [n.label for n in pipe._topology][-1] == "scanning.scan_print"
