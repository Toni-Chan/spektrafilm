"""Write profiles in the exact JSON layout of ``spektrafilm/data/profiles``."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from spektrafilm.profiles.io import profile_to_dict


def _json_safe(data):
    if isinstance(data, dict):
        return {k: _json_safe(v) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        return [_json_safe(v) for v in data]
    if isinstance(data, np.ndarray):
        return _json_safe(data.tolist())
    if isinstance(data, (np.floating, float)):
        return None if not np.isfinite(data) else float(data)
    if isinstance(data, np.integer):
        return int(data)
    return data


def profile_to_json(profile) -> str:
    return json.dumps(_json_safe(profile_to_dict(profile)), indent=4, allow_nan=False)


def save_profile_json(profile, out_dir) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f'{profile.info.stock}.json'
    path.write_text(profile_to_json(profile) + '\n', encoding='utf-8')
    return path
