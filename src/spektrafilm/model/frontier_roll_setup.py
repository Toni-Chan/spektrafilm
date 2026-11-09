"""Optional per-roll density setup (FRT-20).

Outside the core scanner model: the user's workflow finds white/black points
per roll. This helper fits one per-channel affine density correction from all
frames of a roll and applies it to every frame, so it never varies frame to frame.
Percentiles and the green-anchored gain rule are estimates.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

LOW_PERCENTILE = 2.0    # estimate
HIGH_PERCENTILE = 98.0  # estimate


@dataclass(frozen=True)
class RollDensitySetup:
    roll_mid: np.ndarray = field(default_factory=lambda: np.zeros(3))
    target_mid: np.ndarray = field(default_factory=lambda: np.zeros(3))
    gains: np.ndarray = field(default_factory=lambda: np.ones(3))

    @classmethod
    def identity(cls) -> "RollDensitySetup":
        return cls()

    @classmethod
    def fit(cls, frames, target_mid, equalise_gains: bool = True) -> "RollDensitySetup":
        """``frames``: iterable of (..., 3) base-removed instrument densities.
        ``target_mid``: per-channel stock mid-grey density to align to."""
        pooled = np.concatenate([np.asarray(f, dtype=np.float64).reshape(-1, 3) for f in frames])
        pooled = pooled[np.all(np.isfinite(pooled), axis=1)]
        if pooled.size == 0:
            raise ValueError("roll density setup needs at least one finite pixel")
        lo, mid, hi = np.percentile(pooled, [LOW_PERCENTILE, 50.0, HIGH_PERCENTILE], axis=0)
        gains = np.ones(3)
        if equalise_gains:
            spread = np.maximum(hi - lo, 1e-6)
            gains = spread[1] / spread  # green-anchored: keep green's spread, align R and B
        return cls(roll_mid=mid, target_mid=np.asarray(target_mid, dtype=np.float64), gains=gains)

    def apply(self, density: np.ndarray) -> np.ndarray:
        return (np.asarray(density) - self.roll_mid) * self.gains + self.target_mid
