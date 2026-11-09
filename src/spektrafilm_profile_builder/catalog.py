"""Small catalogue rows for downstream apps that keep their own stock list
(e.g. a picker with names, short names and colour swatches)."""

from __future__ import annotations

import re

import colour
import numpy as np

from spektrafilm.config import STANDARD_OBSERVER_CMFS
from spektrafilm.model.illuminants import standard_illuminant


def _swatch(profile) -> str:
    """sRGB hex of the film at mid-scale neutral seen on a D50 light box."""
    ill = standard_illuminant('D50')
    t = 10 ** (-np.nan_to_num(np.asarray(profile.data.midscale_neutral_density, dtype=float)))
    xyz = np.einsum('k,kl->l', t * ill, STANDARD_OBSERVER_CMFS[:]) / np.sum(ill * STANDARD_OBSERVER_CMFS[:, 1])
    rgb = colour.XYZ_to_sRGB(xyz, illuminant=colour.CCS_ILLUMINANTS['CIE 1931 2 Degree Standard Observer']['D50'])
    rgb = np.clip(rgb / max(np.max(rgb), 1e-6) * 0.85, 0, 1)
    return '#' + ''.join(f'{int(round(v * 255)):02x}' for v in rgb)


def catalog_entries(profiles) -> list[dict]:
    rows = []
    for p in profiles:
        name = p.info.name
        short = re.sub(r'^(Fujifilm|Kodak|Ilford)\s+', '', name)
        short = short.replace('(Pro Data Guide)', '(FDG)').strip()
        iso = re.search(r'(\d{2,4})', short)
        kind = 'slide (positive)' if p.info.type == 'positive' else (
            'cine negative' if p.info.use == 'cine' else 'colour negative')
        rows.append({
            'id': p.info.stock, 'name': name, 'shortName': short, 'kind': kind,
            'stage': p.info.stage, 'use': p.info.use, 'type': p.info.type,
            'targetPrint': p.info.target_print, 'iso': int(iso.group(1)) if iso else None,
            'swatch': _swatch(p),
        })
    return rows
