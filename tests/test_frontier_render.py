import colour
import numpy as np
import pytest

from spektrafilm.model.frontier_render import (
    StockReference, apply_gradation, apply_user_offsets, instrument_density,
    remove_base, to_output, tone_map,
)
from spektrafilm.model.scanner_profiles import load_render_profile

pytestmark = pytest.mark.unit
R = load_render_profile("frontier_estimate")
REF = StockReference(d_mid=np.array([0.6, 0.7, 0.8]), gamma=np.array([0.6, 0.62, 0.65]))


def test_base_removed_exactly_once():
    d = instrument_density(np.full(3, 0.5))
    db = remove_base(d, np.full(3, 0.1))
    assert db.base_removed
    with pytest.raises(ValueError):
        remove_base(db, np.full(3, 0.1))
    with pytest.raises(ValueError):
        apply_gradation(d, R, "standard", REF)


def test_tone_curve_monotonic_and_midgray():
    d = np.linspace(0, 3, 200)[:, None] * np.ones(3)
    from spektrafilm.model.frontier_render import InstrumentDensity
    for c in ("soft", "standard", "hard"):
        lin = tone_map(apply_gradation(InstrumentDensity(d, True), R, c, REF), R)
        assert np.all(np.diff(lin, axis=0) > 0)
    mid = tone_map(np.zeros(3), R)
    np.testing.assert_allclose(mid, 0.18, rtol=1e-9)


def test_contrast_ordering():
    from spektrafilm.model.frontier_render import InstrumentDensity
    d = InstrumentDensity(REF.d_mid + 0.3, True)
    soft = apply_gradation(d, R, "soft", REF)
    hard = apply_gradation(d, R, "hard", REF)
    assert np.all(hard > soft)


def test_user_offsets():
    x = np.zeros(3)
    np.testing.assert_allclose(apply_user_offsets(x, (0.1, 0, 0), 0.0), [-0.1, 0, 0])
    np.testing.assert_allclose(apply_user_offsets(x, (0, 0, 0), 1.0), np.full(3, np.log10(2)))


@pytest.mark.parametrize("space", ["sRGB", "AdobeRGB"])
def test_neutral_ramp_and_range(space):
    lin = np.linspace(0.01, 0.9, 32)[:, None] * np.ones(3)
    out = to_output(lin, R, space)
    assert out.min() >= 0 and out.max() <= 1
    name = {"sRGB": "sRGB", "AdobeRGB": "Adobe RGB (1998)"}[space]
    ref = colour.RGB_COLOURSPACES[name].cctf_encoding(lin)
    lab_o = colour.XYZ_to_Lab(colour.RGB_to_XYZ(out, name, apply_cctf_decoding=True))
    lab_r = colour.XYZ_to_Lab(colour.RGB_to_XYZ(ref, name, apply_cctf_decoding=True))
    assert np.max(colour.delta_E(lab_o, lab_r, method="CIE 2000")) < 2.0
    # neutral in -> neutral out
    assert np.max(np.ptp(out, axis=1)) < 1e-4


def test_cctf_applied_once():
    lin = np.full((1, 3), 0.18)
    enc = to_output(lin, R, "sRGB")
    raw = to_output(lin, R, "sRGB", cctf_encoding=False)
    np.testing.assert_allclose(raw, 0.18, atol=1e-4)
    np.testing.assert_allclose(enc, colour.models.eotf_inverse_sRGB(0.18), atol=1e-4)
