"""Fixed positive rendering for the simulated Frontier scanner.

instrument RGB -> instrument density -> single film-base removal
-> per-channel gradation anchored on the stock's mid-grey (a fixed
per-film-type setup, not per-roll auto setup) -> user offsets
-> instrument-to-XYZ matrix -> output colour space with the CCTF applied once.

All numbers come from a :class:`ScannerRenderProfile`; the shipped
``frontier_estimate`` profile is a labelled placeholder.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

import colour
import numpy as np

DisplayRGB = NewType("DisplayRGB", np.ndarray)

OUTPUT_SPACES = {"sRGB": "sRGB", "AdobeRGB": "Adobe RGB (1998)"}
D65_XY = colour.CCS_ILLUMINANTS["CIE 1931 2 Degree Standard Observer"]["D65"]


class InstrumentDensity(np.ndarray):
    """Instrument density array that remembers whether the film base was removed."""

    def __new__(cls, values, base_removed: bool = False):
        obj = np.asarray(values, dtype=np.float64).view(cls)
        obj.base_removed = base_removed
        return obj

    def __array_finalize__(self, obj):
        self.base_removed = getattr(obj, "base_removed", False)


def instrument_density(s: np.ndarray, shading: np.ndarray | None = None) -> InstrumentDensity:
    """-log10(S / shading). ``shading`` is the open-gate (no film) channel signal; default 1."""
    s = np.asarray(s, dtype=np.float64)
    if shading is not None:
        s = s / np.asarray(shading, dtype=np.float64)
    return InstrumentDensity(-np.log10(np.fmax(s, 1e-10)), base_removed=False)


def remove_base(d: InstrumentDensity, base: np.ndarray) -> InstrumentDensity:
    """Subtract the film-base instrument density. May be applied exactly once."""
    if getattr(d, "base_removed", False):
        raise ValueError("film base density has already been removed")
    return InstrumentDensity(np.asarray(d) - np.asarray(base, dtype=np.float64), base_removed=True)


@dataclass(frozen=True)
class StockReference:
    """Per-film-type anchors in base-removed instrument density.

    ``d_mid``: density of a mid-grey exposure; ``gamma``: d(density)/d(log10 exposure).
    """
    d_mid: np.ndarray
    gamma: np.ndarray


def contrast_slope(render, contrast: str) -> float:
    slopes = render.gradation["contrast_slopes"]
    if contrast not in slopes:
        raise ValueError(f"unknown contrast {contrast!r}; expected one of {sorted(slopes)}")
    return float(slopes[contrast])


def apply_gradation(d: InstrumentDensity, render, contrast: str, ref: StockReference) -> np.ndarray:
    """Base-removed instrument density -> log10 relative scene exposure (per channel).

    Mid-grey maps to 0; slope is the stock's instrument gamma scaled by the contrast preset.
    """
    if not getattr(d, "base_removed", False):
        raise ValueError("apply_gradation expects base-removed density")
    k = contrast_slope(render, contrast)
    return (np.asarray(d) - ref.d_mid) / ref.gamma * k


def apply_user_offsets(log_exposure: np.ndarray, density_offset, brightness_offset: float) -> np.ndarray:
    """Operator corrections in the rendered log domain.

    ``density_offset`` (C, M, Y order -> applied to R, G, B) adds print density, so a positive
    value removes that channel's light; ``brightness_offset`` is in stops (positive = brighter).
    """
    off = np.asarray(density_offset, dtype=np.float64)
    return log_exposure - off + float(brightness_offset) * np.log10(2.0)


def tone_map(log_exposure: np.ndarray, render) -> np.ndarray:
    """log10 relative exposure -> linear display-referred value with a highlight roll-off."""
    g = render.gradation
    mid = float(g.get("midgray_out", 0.18))
    w = float(g.get("white_rolloff", 6.0))
    lin = mid * 10.0 ** np.asarray(log_exposure)
    # extended Reinhard, rescaled so mid-grey stays at ``mid``
    def r(x):
        return x * (1.0 + x / w**2) / (1.0 + x)
    scale = mid / r(mid)
    return np.clip(r(lin) * scale, 0.0, None)


def to_output(rendered: np.ndarray, render, output_space: str, *, cctf_encoding: bool = True) -> DisplayRGB:
    """Linear rendered instrument RGB -> encoded output RGB in [0, 1]."""
    if output_space not in OUTPUT_SPACES:
        raise ValueError(f"unknown output space {output_space!r}")
    m = render.matrix_instrument_to_xyz
    if m is None:
        m = colour.RGB_COLOURSPACES["sRGB"].matrix_RGB_to_XYZ
    xyz = np.asarray(rendered, dtype=np.float64) @ np.asarray(m).T
    rgb = colour.XYZ_to_RGB(
        xyz, OUTPUT_SPACES[output_space], illuminant=D65_XY,
        chromatic_adaptation_transform=None, apply_cctf_encoding=False,
    )
    rgb = np.clip(rgb, 0.0, 1.0)
    if cctf_encoding:
        rgb = colour.RGB_COLOURSPACES[OUTPUT_SPACES[output_space]].cctf_encoding(rgb)
    return DisplayRGB(np.clip(rgb, 0.0, 1.0))
