"""Print CIE xy, sRGB and Adobe RGB of the Frontier LED presets (display only).

The simulation itself never uses these RGB triplets; it works on the
380-780 nm spectral grid.
"""
from __future__ import annotations

import colour
import numpy as np

from spektrafilm.config import STANDARD_OBSERVER_CMFS
from spektrafilm.model.scanner_profiles import list_profiles, load_capture_profile


def main():
    cmfs = np.asarray(STANDARD_OBSERVER_CMFS[:])
    for pid in list_profiles("capture"):
        prof = load_capture_profile(pid)
        print(pid)
        for ch, k in prof.led_spd.items():
            xyz = k.values @ cmfs
            xyz = xyz / xyz[1]
            xy = colour.XYZ_to_xy(xyz)
            srgb = colour.XYZ_to_RGB(xyz, "sRGB", apply_cctf_encoding=False)
            argb = colour.XYZ_to_RGB(xyz, "Adobe RGB (1998)", apply_cctf_encoding=False)
            fmt = lambda v: "(" + ", ".join(f"{x:+.3f}" for x in v) + ")"
            print(f"  {ch}: xy={fmt(xy)} sRGB_lin={fmt(srgb / np.max(srgb))} AdobeRGB_lin={fmt(argb / np.max(argb))}")


if __name__ == "__main__":
    main()
