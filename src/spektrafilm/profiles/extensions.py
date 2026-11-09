"""Optional per-stock *profile extensions* (sidecar files).

Profile JSONs under ``spektrafilm/data/profiles`` are a shared format: the
upstream loader builds ``ProfileData(**data)`` and rejects unknown keys, and
downstream programs (e.g. SpektraLab's C++ loader, which treats every
``profiles/*.json`` as a film stock) read the same files. Data that only this
fork's runtime understands therefore lives in a separate *sidecar* directory,
``spektrafilm/data/profile_extensions/<stock>.json``, that other programs
never look at.

Schema (version 1)::

    {
      "stock": "fujifilm_pro_400h_fdg",
      "version": 1,
      "inhibitor_layers": [
        {
          "name": "cyan",                # free label
          "target": "r",                 # receiving layer: "r", "g" or "b"
          "reference": "g",              # neutral-equivalent layer (optional, default "g")
          "wavelengths": [380, ..., 780],   # must equal the profile grid
          "log_sensitivity": [...],      # log10, normalised: 18.4 % grey -> raw 1
          "amount_default": 0.3,         # inhibition strength (log exposure per unit silver density)
          "label": "estimate",           # provenance of amount_default
          "source": "...",               # provenance of the sensitivity curve
          "notes": "..."                 # optional free text
        }
      ]
    }

An inhibitor layer is an emulsion layer that forms *no image dye*: its
developed silver only releases development inhibitor into ``target``. The
runtime (``spektrafilm.model.couplers.InhibitorExposure``) lowers the target
layer's log exposure by ``amount * [D(log E_layer) - D(log E_reference)]``, the
departure of the layer's silver from what a neutral exposure of the same
brightness would give (data-sheet curves already include the neutral level). A missing sidecar means the feature is off and the render
is bit-identical to a build without this module.
"""

from __future__ import annotations

import importlib.resources as pkg_resources
import json
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Mapping

import numpy as np

EXTENSIONS_PACKAGE = 'spektrafilm.data.profile_extensions'
EXTENSION_SCHEMA_VERSION = 1
_TARGET_INDEX = {'r': 0, 'g': 1, 'b': 2}


@dataclass(frozen=True)
class InhibitorLayer:
    name: str
    target: str
    wavelengths: np.ndarray
    log_sensitivity: np.ndarray
    amount_default: float
    reference: str = 'g'
    label: str = 'estimate'
    source: str = ''
    notes: str = ''
    extra: dict = field(default_factory=dict)

    @property
    def target_index(self) -> int:
        return _TARGET_INDEX[self.target]

    @property
    def reference_index(self) -> int:
        return _TARGET_INDEX[self.reference]

    @property
    def sensitivity(self) -> np.ndarray:
        """Linear spectral sensitivity on the profile grid (NaN -> 0)."""
        return np.nan_to_num(10.0 ** self.log_sensitivity)


@dataclass(frozen=True)
class ProfileExtension:
    stock: str
    version: int = EXTENSION_SCHEMA_VERSION
    inhibitor_layers: tuple[InhibitorLayer, ...] = ()

    def inhibitor(self, name: str = 'cyan') -> InhibitorLayer | None:
        for layer in self.inhibitor_layers:
            if layer.name == name:
                return layer
        return None


_LAYER_KEYS = {'name', 'target', 'reference', 'wavelengths', 'log_sensitivity', 'amount_default', 'label', 'source', 'notes'}


def _layer_from_dict(payload: Mapping[str, Any], stock: str) -> InhibitorLayer:
    try:
        target = str(payload['target']).lower()
        wl = np.asarray(payload['wavelengths'], dtype=float)
        ls = np.asarray([np.nan if v is None else v for v in payload['log_sensitivity']], dtype=float)
        amount = float(payload['amount_default'])
        name = str(payload['name'])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid profile extension '{stock}': bad inhibitor layer ({exc})") from None
    reference = str(payload.get('reference', 'g')).lower()
    if target not in _TARGET_INDEX or reference not in _TARGET_INDEX:
        raise ValueError(f"Invalid profile extension '{stock}': target/reference must be r, g or b")
    if reference == target:
        raise ValueError(f"Invalid profile extension '{stock}': reference must differ from target")
    if wl.ndim != 1 or ls.shape != wl.shape:
        raise ValueError(f"Invalid profile extension '{stock}': wavelengths/log_sensitivity shape mismatch")
    if not np.isfinite(amount) or amount < 0:
        raise ValueError(f"Invalid profile extension '{stock}': amount_default must be finite and >= 0")
    return InhibitorLayer(
        name=name, target=target, reference=reference, wavelengths=wl, log_sensitivity=ls, amount_default=amount,
        label=str(payload.get('label', 'estimate')), source=str(payload.get('source', '')),
        notes=str(payload.get('notes', '')),
        extra={k: v for k, v in payload.items() if k not in _LAYER_KEYS},
    )


def profile_extension_from_dict(payload: Mapping[str, Any]) -> ProfileExtension:
    if not isinstance(payload, Mapping):
        raise TypeError('profile extension must be a mapping')
    stock = str(payload.get('stock', ''))
    version = int(payload.get('version', EXTENSION_SCHEMA_VERSION))
    if version > EXTENSION_SCHEMA_VERSION:
        raise ValueError(f"Profile extension '{stock}' has unsupported version {version}")
    layers = tuple(_layer_from_dict(p, stock) for p in payload.get('inhibitor_layers', []))
    return ProfileExtension(stock=stock, version=version, inhibitor_layers=layers)


def profile_extension_to_dict(ext: ProfileExtension) -> dict:
    def _f(a):
        return [None if not np.isfinite(v) else float(v) for v in np.asarray(a, dtype=float)]
    layers = []
    for layer in ext.inhibitor_layers:
        d = {
            'name': layer.name, 'target': layer.target, 'reference': layer.reference,
            'amount_default': float(layer.amount_default), 'label': layer.label,
            'source': layer.source,
        }
        if layer.notes:
            d['notes'] = layer.notes
        d.update(layer.extra)
        d['wavelengths'] = _f(layer.wavelengths)
        d['log_sensitivity'] = _f(layer.log_sensitivity)
        layers.append(d)
    return {'stock': ext.stock, 'version': int(ext.version), 'inhibitor_layers': layers}


@lru_cache(maxsize=None)
def load_profile_extension(stock: str | None) -> ProfileExtension | None:
    """Return the sidecar for ``stock`` or ``None`` when there is none."""
    if not stock:
        return None
    try:
        resource = pkg_resources.files(EXTENSIONS_PACKAGE) / f'{stock}.json'
        if not resource.is_file():
            return None
        with resource.open('r') as file:
            payload = json.load(file)
    except (FileNotFoundError, ModuleNotFoundError):
        return None
    return profile_extension_from_dict(payload)


def list_profile_extensions() -> list[str]:
    try:
        package = pkg_resources.files(EXTENSIONS_PACKAGE)
        return sorted(e.name[:-5] for e in package.iterdir() if e.name.endswith('.json'))
    except (FileNotFoundError, ModuleNotFoundError):
        return []


__all__ = [
    'EXTENSION_SCHEMA_VERSION', 'InhibitorLayer', 'ProfileExtension', 'load_profile_extension',
    'list_profile_extensions', 'profile_extension_from_dict', 'profile_extension_to_dict',
]
