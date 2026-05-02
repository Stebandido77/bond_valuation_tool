"""
market_data.interpolation
=========================

Interpolation strategies for curve construction.

The ``Interpolator`` protocol takes (xs, ys, x) and returns the interpolated
y. Three strategies are provided:

    - LinearInterpolator: linear in zero rate
    - LogLinearDFInterpolator: linear in log of discount factor (i.e. linear
      in r*t — this is what most fixed-income trading systems use because it
      reproduces forward rates that are piecewise-constant)
    - CubicSplineInterpolator: natural cubic spline for smooth curves

For the tool's UI we expose linear by default; the others are available
programmatically.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np


class Interpolator(Protocol):
    def interpolate(self, xs: np.ndarray, ys: np.ndarray, x: float) -> float: ...


class LinearInterpolator:
    """Piecewise linear, flat extrapolation."""

    def interpolate(self, xs: np.ndarray, ys: np.ndarray, x: float) -> float:
        if x <= xs[0]:
            return float(ys[0])
        if x >= xs[-1]:
            return float(ys[-1])
        return float(np.interp(x, xs, ys))


class LogLinearDFInterpolator:
    """Linear in log-DF.

    Given pillars ``(t_i, r_i)``, build ``ln DF_i = -r_i * t_i / 365`` and
    linearly interpolate that, which yields piecewise-constant forwards.
    The result is converted back to a zero rate so the caller can keep
    working in rate space.
    """

    BASIS = 365.0

    def interpolate(self, xs: np.ndarray, ys: np.ndarray, x: float) -> float:
        ts = xs / self.BASIS
        log_df = -ys * ts
        if x <= xs[0]:
            return float(ys[0])
        if x >= xs[-1]:
            return float(ys[-1])
        ld = float(np.interp(x, xs, log_df))
        t = x / self.BASIS
        if t == 0:
            return float(ys[0])
        return float(-ld / t)


class CubicSplineInterpolator:
    """Natural cubic spline; falls back to linear if scipy is unavailable."""

    def __init__(self):
        try:
            from scipy.interpolate import CubicSpline  # type: ignore
            self._cs = CubicSpline
            self._available = True
        except Exception:
            self._available = False

    def interpolate(self, xs: np.ndarray, ys: np.ndarray, x: float) -> float:
        if not self._available or len(xs) < 4:
            return LinearInterpolator().interpolate(xs, ys, x)
        if x <= xs[0]:
            return float(ys[0])
        if x >= xs[-1]:
            return float(ys[-1])
        spline = self._cs(xs, ys, bc_type="natural")
        return float(spline(x))


INTERPOLATORS = {
    "linear": LinearInterpolator,
    "log_linear_df": LogLinearDFInterpolator,
    "cubic_spline": CubicSplineInterpolator,
}
