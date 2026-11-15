# Baseline before Frontier work

Commit: `3bb2c2d` (fix: vlog midgray exposure)
Environment: Python 3.13.5, numpy 2.5.4, numba 0.68.1, colour-science 0.4.7

Command: `python -m pytest -q`
Result: **5 failed, 774 passed, 1 skipped**. These failures exist before any Frontier change:

- `tests/gui/test_layout.py::test_build_controls_panel_places_gamut_compression_sections_on_advanced_tab` (FakeVBoxLayout.addWidget TypeError)
- `tests/test_lut_mode.py::test_lut_mode_digest_disables_every_dangerous_effect` (references removed `GrainParams.mult_usm_amount`)
- `tests/test_regression_baselines.py::...[print_rgb_portra_endura_gray_ramp16]`
- `tests/test_regression_baselines.py::...[print_rgb_fuji_crystal_gray_ramp16]`
- `tests/test_regression_baselines.py::...[print_rgb_portra_endura_green_patch8]`

Rule: Frontier tickets must not change this result set. Do not regenerate
baselines in `tests/baselines/` as part of Frontier work; a baseline
regeneration needs its own commit and an explanation.
