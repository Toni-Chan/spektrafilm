import copy
import json

import numpy as np
import pytest

from spektrafilm.model.scanner_profiles import (
    MissingProvenanceError,
    capture_profile_from_dict,
    gaussian_spd,
    grid_wavelengths,
    list_profiles,
    load_capture_profile,
    load_render_profile,
    profile_hash,
    render_profile_from_dict,
    save_profile,
)

pytestmark = pytest.mark.unit


def test_all_shipped_profiles_load():
    caps = list_profiles("capture")
    assert len(caps) == 6
    for pid in caps:
        p = load_capture_profile(pid)
        k = p.channel_kernels()
        assert k.shape == (grid_wavelengths().size, 3)
        assert np.all(k >= 0)
        assert p.provenance.label in ("estimate", "community")
    assert load_render_profile("frontier_estimate").matrix_instrument_to_xyz.shape == (3, 3)


def test_capture_round_trip(tmp_path):
    p = load_capture_profile("frontier_sp500_community_a")
    out = tmp_path / "p.json"
    save_profile(p, out)
    q = capture_profile_from_dict(json.loads(out.read_text()))
    assert profile_hash(p) == profile_hash(q)
    np.testing.assert_array_equal(p.channel_kernels(), q.channel_kernels())


def test_render_round_trip(tmp_path):
    p = load_render_profile("frontier_estimate")
    out = tmp_path / "r.json"
    save_profile(p, out)
    assert p == render_profile_from_dict(json.loads(out.read_text()))


def test_hash_stable_and_sensitive():
    a = load_capture_profile("frontier_sp500_community_a")
    assert profile_hash(a) == profile_hash(load_capture_profile("frontier_sp500_community_a"))
    raw = copy.deepcopy(a.raw)
    raw["led_spd"]["G"]["gaussian"]["peak_nm"] += 1.0
    assert profile_hash(capture_profile_from_dict(raw)) != profile_hash(a)


def test_missing_provenance_raises():
    raw = copy.deepcopy(load_capture_profile("frontier_sp500_community_a").raw)
    del raw["led_spd"]["R"]["provenance"]
    with pytest.raises(MissingProvenanceError):
        capture_profile_from_dict(raw)
    raw = copy.deepcopy(load_capture_profile("frontier_sp500_community_a").raw)
    del raw["adc_bits"]["provenance"]
    with pytest.raises(MissingProvenanceError):
        capture_profile_from_dict(raw)


def test_effective_kernels_override():
    raw = copy.deepcopy(load_capture_profile("frontier_sp500_community_a").raw)
    pv = {"label": "estimate", "source": "test"}
    raw["effective_kernels"] = {c: {"constant": v, "provenance": pv} for c, v in zip("RGB", (1.0, 2.0, 3.0))}
    k = capture_profile_from_dict(raw).channel_kernels()
    np.testing.assert_allclose(k[0], [1.0, 2.0, 3.0])


def test_partial_table_zero_filled_with_warning():
    raw = copy.deepcopy(load_capture_profile("frontier_sp500_community_a").raw)
    raw["sensor_qe"]["wavelengths_nm"] = [450, 650]
    raw["sensor_qe"]["values"] = [1.0, 1.0]
    with pytest.warns(UserWarning):
        p = capture_profile_from_dict(raw)
    assert p.sensor_qe.values[0] == 0.0


def test_gaussian_spd_fwhm_and_skew():
    wl = np.arange(500.0, 760.0, 0.1)
    s = gaussian_spd(630.0, 20.0, wl)
    above = wl[s >= 0.5]
    assert abs((above[-1] - above[0]) - 20.0) < 0.3
    sk = gaussian_spd(630.0, 20.0, wl, skew=0.3)
    assert wl[np.argmax(sk)] == pytest.approx(630.0, abs=0.1)
    assert np.sum(sk[wl > 630]) > np.sum(sk[wl < 630])
