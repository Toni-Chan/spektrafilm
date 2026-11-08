"""Typed, provenance-checked scanner capture and render profiles.

Profiles are JSON files under ``spektrafilm/data/scanners/capture`` and
``spektrafilm/data/scanners/render``. Every numeric field carries a
``provenance`` block so that estimates can later be replaced with measured
data without code changes (see ``docs/frontier/evidence.md``).

Spectral data can be given either as a table::

    {"wavelengths_nm": [...], "values": [...], "provenance": {...}}

or as a Gaussian LED model::

    {"gaussian": {"peak_nm": 630, "fwhm_nm": 20, "skew": 0.0}, "provenance": {...}}

All spectra are resampled onto the simulation grid (``config.SPECTRAL_SHAPE``).
"""
from __future__ import annotations

import hashlib
import json
import warnings
from dataclasses import dataclass, field
from importlib import resources
from typing import Literal

import numpy as np

from spektrafilm.config import SPECTRAL_SHAPE

ProvenanceLabel = Literal["official", "patent", "community", "estimate", "measured"]
ALLOWED_LABELS = ("official", "patent", "community", "estimate", "measured")
CHANNELS = ("R", "G", "B")


def grid_wavelengths() -> np.ndarray:
    return np.asarray(SPECTRAL_SHAPE.wavelengths, dtype=np.float64)


class MissingProvenanceError(ValueError):
    """Raised when a numeric profile field has no provenance."""


@dataclass(frozen=True)
class Provenance:
    label: ProvenanceLabel
    source: str
    locator: str = ""
    notes: str = ""

    def __post_init__(self):
        if self.label not in ALLOWED_LABELS:
            raise ValueError(f"invalid provenance label {self.label!r}")
        if not self.source:
            raise MissingProvenanceError("provenance.source must not be empty")

    @classmethod
    def from_dict(cls, d, where: str) -> "Provenance":
        if not isinstance(d, dict) or "label" not in d or "source" not in d:
            raise MissingProvenanceError(f"missing provenance at {where}")
        return cls(label=d["label"], source=d["source"],
                   locator=d.get("locator", ""), notes=d.get("notes", ""))

    def to_dict(self) -> dict:
        return {"label": self.label, "source": self.source,
                "locator": self.locator, "notes": self.notes}


@dataclass(frozen=True)
class SpectralKernel:
    wavelengths_nm: np.ndarray
    values: np.ndarray
    provenance: Provenance

    def __eq__(self, other):
        return (isinstance(other, SpectralKernel)
                and np.array_equal(self.wavelengths_nm, other.wavelengths_nm)
                and np.array_equal(self.values, other.values)
                and self.provenance == other.provenance)

    __hash__ = None


@dataclass(frozen=True)
class ScannerCaptureProfile:
    id: str
    led_spd: dict
    filters: list
    sensor_qe: SpectralKernel | None
    effective_kernels: dict | None
    mtf: dict
    pixel_shift: dict
    noise: dict
    adc_bits: int | None
    provenance: Provenance
    description: str = ""
    raw: dict = field(default_factory=dict, compare=False, repr=False)

    def channel_kernels(self) -> np.ndarray:
        """Per-channel spectral responsivity on the simulation grid, shape (n_wl, 3) in R,G,B order.

        ``effective_kernels`` (if present) override LED x filters x QE.
        """
        if self.effective_kernels:
            return np.stack([self.effective_kernels[c].values for c in CHANNELS], axis=1)
        transmission = np.ones_like(grid_wavelengths())
        for f in self.filters:
            transmission = transmission * f.values
        qe = self.sensor_qe.values if self.sensor_qe is not None else 1.0
        return np.stack([self.led_spd[c].values * transmission * qe for c in CHANNELS], axis=1)


@dataclass(frozen=True)
class ScannerRenderProfile:
    id: str
    gradation: dict
    balance: dict
    matrix_instrument_to_xyz: np.ndarray | None
    provenance: Provenance
    description: str = ""
    raw: dict = field(default_factory=dict, compare=False, repr=False)

    def __eq__(self, other):
        return isinstance(other, ScannerRenderProfile) and profile_hash(self) == profile_hash(other)

    __hash__ = None


# ---------------------------------------------------------------- spectra

def gaussian_spd(peak_nm: float, fwhm_nm: float, wl: np.ndarray, skew: float = 0.0) -> np.ndarray:
    """Unit-peak Gaussian LED spectrum.

    ``skew`` != 0 gives a split Gaussian: the long-wavelength half width is
    ``fwhm*(1+skew)/2`` and the short one ``fwhm*(1-skew)/2``.
    """
    wl = np.asarray(wl, dtype=np.float64)
    if fwhm_nm <= 0:
        raise ValueError("fwhm_nm must be positive")
    if not -1.0 < skew < 1.0:
        raise ValueError("skew must be in (-1, 1)")
    sigma = fwhm_nm / (2.0 * np.sqrt(2.0 * np.log(2.0)))
    sigma_lo = sigma * (1.0 - skew)
    sigma_hi = sigma * (1.0 + skew)
    s = np.where(wl < peak_nm, sigma_lo, sigma_hi)
    return np.exp(-0.5 * ((wl - peak_nm) / s) ** 2)


def resample_to_grid(wavelengths_nm, values, where: str = "") -> np.ndarray:
    wl = np.asarray(wavelengths_nm, dtype=np.float64)
    v = np.asarray(values, dtype=np.float64)
    if wl.shape != v.shape or wl.ndim != 1 or wl.size < 2:
        raise ValueError(f"bad spectral table at {where}")
    order = np.argsort(wl)
    wl, v = wl[order], v[order]
    grid = grid_wavelengths()
    if grid[0] < wl[0] or grid[-1] > wl[-1]:
        warnings.warn(f"spectrum at {where} does not cover {grid[0]:.0f}-{grid[-1]:.0f} nm; zero-filled outside data",
                      stacklevel=3)
    return np.interp(grid, wl, v, left=0.0, right=0.0)


def _kernel_from_dict(d: dict, where: str) -> SpectralKernel:
    prov = Provenance.from_dict(d.get("provenance"), where)
    if "gaussian" in d:
        g = d["gaussian"]
        values = gaussian_spd(float(g["peak_nm"]), float(g["fwhm_nm"]), grid_wavelengths(),
                              float(g.get("skew", 0.0)))
    elif "wavelengths_nm" in d and "values" in d:
        values = resample_to_grid(d["wavelengths_nm"], d["values"], where)
    elif "constant" in d:
        values = np.full_like(grid_wavelengths(), float(d["constant"]))
    else:
        raise ValueError(f"spectral kernel at {where} needs 'gaussian', a table, or 'constant'")
    return SpectralKernel(grid_wavelengths(), values, prov)


def _check_numeric_has_provenance(node, where: str, inherited: bool = False):
    """Every dict that holds numbers must have a provenance on itself or an ancestor block."""
    if isinstance(node, dict):
        has = inherited or ("provenance" in node)
        if "provenance" in node:
            Provenance.from_dict(node["provenance"], where)
        for k, v in node.items():
            if k == "provenance":
                continue
            if isinstance(v, (int, float)) and not isinstance(v, bool) and not has:
                raise MissingProvenanceError(f"numeric field {where}.{k} has no provenance")
            if isinstance(v, list) and any(isinstance(x, (int, float)) for x in v) and not has:
                raise MissingProvenanceError(f"numeric field {where}.{k} has no provenance")
            _check_numeric_has_provenance(v, f"{where}.{k}", has)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _check_numeric_has_provenance(v, f"{where}[{i}]", inherited)


# ---------------------------------------------------------------- loading

def capture_profile_from_dict(d: dict) -> ScannerCaptureProfile:
    pid = d["id"]
    _check_numeric_has_provenance({k: v for k, v in d.items() if k != "provenance"}, pid,
                                  inherited=False)
    led = {c: _kernel_from_dict(d["led_spd"][c], f"{pid}.led_spd.{c}") for c in CHANNELS}
    filters = [_kernel_from_dict(f, f"{pid}.filters[{i}]") for i, f in enumerate(d.get("filters", []))]
    qe = _kernel_from_dict(d["sensor_qe"], f"{pid}.sensor_qe") if d.get("sensor_qe") else None
    eff = None
    if d.get("effective_kernels"):
        eff = {c: _kernel_from_dict(d["effective_kernels"][c], f"{pid}.effective_kernels.{c}")
               for c in CHANNELS}
    adc = d.get("adc_bits")
    return ScannerCaptureProfile(
        id=pid,
        led_spd=led,
        filters=filters,
        sensor_qe=qe,
        effective_kernels=eff,
        mtf=d.get("mtf", {}),
        pixel_shift=d.get("pixel_shift", {}),
        noise=d.get("noise", {}),
        adc_bits=None if adc is None else int(adc["value"]),
        provenance=Provenance.from_dict(d.get("provenance"), pid),
        description=d.get("description", ""),
        raw=d,
    )


def render_profile_from_dict(d: dict) -> ScannerRenderProfile:
    pid = d["id"]
    _check_numeric_has_provenance({k: v for k, v in d.items() if k != "provenance"}, pid)
    m = d.get("matrix_instrument_to_xyz")
    matrix = None if m is None else np.asarray(m["value"], dtype=np.float64).reshape(3, 3)
    return ScannerRenderProfile(
        id=pid,
        gradation=d.get("gradation", {}),
        balance=d.get("balance", {}),
        matrix_instrument_to_xyz=matrix,
        provenance=Provenance.from_dict(d.get("provenance"), pid),
        description=d.get("description", ""),
        raw=d,
    )


def _read_json(kind: str, pid: str) -> dict:
    path = resources.files("spektrafilm.data").joinpath("scanners", kind, f"{pid}.json")
    if not path.is_file():
        raise FileNotFoundError(f"scanner {kind} profile {pid!r} not found")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def list_profiles(kind: Literal["capture", "render"]) -> list[str]:
    folder = resources.files("spektrafilm.data").joinpath("scanners", kind)
    return sorted(p.name[:-5] for p in folder.iterdir() if p.name.endswith(".json"))


def load_capture_profile(id: str) -> ScannerCaptureProfile:
    return capture_profile_from_dict(_read_json("capture", id))


def load_render_profile(id: str) -> ScannerRenderProfile:
    return render_profile_from_dict(_read_json("render", id))


def save_profile(profile, path) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(profile.raw, fh, indent=2, sort_keys=True)
        fh.write("\n")


# ---------------------------------------------------------------- hashing

def _canonical(obj):
    if isinstance(obj, np.ndarray):
        return [_canonical(x) for x in obj.tolist()]
    if isinstance(obj, (np.floating, float)):
        return float(repr(float(obj))) if np.isfinite(obj) else str(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, dict):
        return {str(k): _canonical(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_canonical(x) for x in obj]
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _canonical(getattr(obj, k)) for k in obj.__dataclass_fields__ if k != "raw"}
    return obj


def profile_hash(obj) -> str:
    """sha256 of the canonical JSON form of a profile (or any dataclass/array)."""
    payload = json.dumps(_canonical(obj), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
