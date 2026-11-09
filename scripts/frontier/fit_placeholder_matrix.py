"""Fit a placeholder instrument->XYZ matrix for a Frontier capture profile.

Synthetic scene patches (random linear sRGB colours) are exposed onto the
default film stock with spektrafilm's filming stage, captured with the
chosen Frontier capture profile and rendered with the estimate gradation;
a 3x3 least-squares matrix maps the rendered instrument RGB to the scene
XYZ. The result is still an ``estimate`` (it inherits every placeholder
upstream) and should be replaced by a chart-based fit (FRT-24).

Usage: python scripts/frontier/fit_placeholder_matrix.py [capture_profile_id]
"""
from __future__ import annotations

import sys

import colour
import numpy as np

from spektrafilm.runtime.params_builder import init_params
from spektrafilm.runtime.pipeline import SimulationPipeline


def main(capture_id: str = "frontier_sp500_community_a") -> None:
    rng = np.random.default_rng(0)
    scene = rng.uniform(0.02, 0.8, (24, 24, 3))
    params = init_params()
    params.scanner.method = "frontier_sp500" if "sp500" in capture_id else "frontier_sp3000"
    params.scanner.capture_profile = capture_id
    params.io.input_color_space = "sRGB"
    params.io.output_cctf_encoding = False
    params.debug.deactivate_spatial_effects = True
    params.debug.deactivate_stochastic_effects = True
    params.camera.auto_exposure = False
    sim = SimulationPipeline(params)
    rendered = sim.process(scene, collect="frontier_rendered").reshape(-1, 3)
    xyz = colour.RGB_to_XYZ(scene.reshape(-1, 3), "sRGB", apply_cctf_decoding=False)
    m, *_ = np.linalg.lstsq(rendered, xyz, rcond=None)
    print(np.array2string(m.T, precision=6, separator=", "))


if __name__ == "__main__":
    main(*sys.argv[1:])
