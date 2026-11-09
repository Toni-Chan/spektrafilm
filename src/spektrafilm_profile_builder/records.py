"""Raw data-sheet records.

A record is a folder of headerless ``x, y`` CSV files in the historical
spektrafilm raw-data layout:

=================================  =========================================
file                               content
=================================  =========================================
``log_sensitivity_{r,g,b}.csv``    wavelength [nm], log10 spectral sensitivity
``density_curve_{r,g,b}.csv``      log10 exposure [lux s], total density
``dye_density_{c,m,y}.csv``        wavelength [nm], spectral dye density
                                   (reversal films, and any stock whose sheet
                                   separates the dyes)
``dye_density_{mid,min}.csv``      wavelength [nm], mid-scale neutral and
                                   minimum spectral density (colour negatives)
``info.txt``                       free text; the first line is the stock name,
                                   ``Key: value`` lines are parsed
=================================  =========================================

Other files (``mtf.csv``, ``log_sensitivity_cyan_layer.csv``...) are kept
for reference and ignored by the builder.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .spectral import WAVELENGTHS, interpolate, read_xy_csv


@dataclass
class RawRecord:
    folder: Path
    name: str
    info: dict
    log_sensitivity: np.ndarray                 # (n_wl, 3) on WAVELENGTHS, NaN outside data
    density_curves_xy: list                     # 3 x (2, n) raw points (log H, total density)
    dye_density_cmy: np.ndarray | None = None   # (n_wl, 3)
    dye_density_min: np.ndarray | None = None   # (n_wl,)
    dye_density_mid: np.ndarray | None = None   # (n_wl,)
    wavelengths: np.ndarray = field(default_factory=lambda: WAVELENGTHS.copy())

    @property
    def has_cmy_dyes(self) -> bool:
        return self.dye_density_cmy is not None

    @property
    def has_mid_min(self) -> bool:
        return self.dye_density_min is not None and self.dye_density_mid is not None

    @property
    def guessed_type(self) -> str:
        t = self.info.get('type', '').strip().lower()
        if t in ('negative', 'positive'):
            return t
        return 'positive' if self.has_cmy_dyes and not self.has_mid_min else 'negative'


def _parse_info(path: Path):
    if not path.exists():
        return '', {}
    lines = path.read_text(encoding='utf-8').splitlines()
    name = lines[0].strip() if lines else ''
    info = {}
    for line in lines[1:]:
        m = re.match(r'^([A-Za-z][A-Za-z /()-]*?):\s*(.+)$', line)
        if m and not line.startswith(' '):
            info[m.group(1).strip().lower()] = m.group(2).strip()
    return name, info


def load_record(folder) -> RawRecord:
    folder = Path(folder)
    name, info = _parse_info(folder / 'info.txt')
    wl = WAVELENGTHS

    def spectral(fname):
        p = folder / fname
        return interpolate(read_xy_csv(p), wl) if p.exists() else None

    ls = [spectral(f'log_sensitivity_{c}.csv') for c in 'rgb']
    if any(x is None for x in ls):
        raise FileNotFoundError(f'{folder}: log_sensitivity_r/g/b.csv are required')
    dc = []
    for c in 'rgb':
        p = folder / f'density_curve_{c}.csv'
        if not p.exists():
            raise FileNotFoundError(f'{folder}: density_curve_r/g/b.csv are required')
        dc.append(read_xy_csv(p))
    cmy = [spectral(f'dye_density_{c}.csv') for c in 'cmy']
    cmy = np.stack(cmy, axis=1) if all(x is not None for x in cmy) else None
    return RawRecord(
        folder=folder, name=name or folder.name, info=info,
        log_sensitivity=np.stack(ls, axis=1), density_curves_xy=dc,
        dye_density_cmy=cmy,
        dye_density_min=spectral('dye_density_min.csv'),
        dye_density_mid=spectral('dye_density_mid.csv'),
    )
