"""Helpers for anemometer orientation (direction) correction."""

from __future__ import annotations

import numpy as np

# One-degree bins covering [0, 360); 360 edges yield 360 bins.
DIR_BIN_EDGES = np.arange(0.0, 361.0, 1.0)
DIR_BIN_CENTERS = 0.5 * (DIR_BIN_EDGES[:-1] + DIR_BIN_EDGES[1:])


def wrap_degrees(values: np.ndarray) -> np.ndarray:
    """Wrap angles into [0, 360)."""
    return np.mod(np.asarray(values, dtype=float), 360.0)


def direction_density_histogram(directions: np.ndarray) -> np.ndarray:
    """Normalized 1° histogram of wind directions (sums to 1 when non-empty)."""
    finite = wrap_degrees(directions)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return np.zeros(len(DIR_BIN_CENTERS), dtype=float)
    counts, _ = np.histogram(finite, bins=DIR_BIN_EDGES)
    total = float(counts.sum())
    if total <= 0:
        return np.zeros_like(counts, dtype=float)
    return counts.astype(float) / total


def peak_normalize(density: np.ndarray) -> np.ndarray:
    """Scale a density histogram so its peak is 1 (for comparable overlays)."""
    values = np.asarray(density, dtype=float)
    peak = float(np.nanmax(values)) if values.size else 0.0
    if not np.isfinite(peak) or peak <= 0:
        return values
    return values / peak


def circular_smooth(density: np.ndarray, sigma_deg: float = 8.0) -> np.ndarray:
    """Circular Gaussian smooth of a 1°-bin density histogram."""
    values = np.asarray(density, dtype=float)
    n = values.size
    if n == 0:
        return values
    sigma = max(float(sigma_deg), 0.5)
    index = np.arange(n)
    kernel = np.exp(-0.5 * (np.minimum(index, n - index) ** 2) / (sigma**2))
    kernel /= kernel.sum()
    return np.fft.ifft(np.fft.fft(values) * np.fft.fft(kernel)).real


def density_correlation(
    reference: np.ndarray,
    other: np.ndarray,
) -> float:
    """Pearson correlation between two density histograms in ``[-1, 1]``."""
    ref = np.asarray(reference, dtype=float)
    mov = np.asarray(other, dtype=float)
    if ref.shape != mov.shape or ref.size == 0:
        return float("nan")
    if float(ref.sum()) <= 0 or float(mov.sum()) <= 0:
        return float("nan")
    ref = ref - float(ref.mean())
    mov = mov - float(mov.mean())
    denom = float(np.linalg.norm(ref) * np.linalg.norm(mov))
    if denom <= 0:
        return float("nan")
    return float(np.dot(ref, mov) / denom)


def best_rotation_degrees(
    correct_density: np.ndarray,
    incorrect_density: np.ndarray,
) -> int:
    """Rotation in degrees to add to incorrect dirs so they best match correct.

    Uses circular cross-correlation on density histograms and returns the
    shift in ``[-180, 180]``.
    """
    reference = np.asarray(correct_density, dtype=float)
    moving = np.asarray(incorrect_density, dtype=float)
    if reference.shape != moving.shape or reference.size == 0:
        return 0
    if not np.isfinite(reference).any() or not np.isfinite(moving).any():
        return 0
    if float(reference.sum()) <= 0 or float(moving.sum()) <= 0:
        return 0

    ref = reference - float(reference.mean())
    mov = moving - float(moving.mean())
    correlation = np.fft.ifft(np.fft.fft(ref) * np.conj(np.fft.fft(mov))).real
    shift = int(np.argmax(correlation))
    n = reference.size
    if shift > n // 2:
        shift -= n

    print(np.max(correlation))
    return int(np.clip(shift, -180, 180))


def rotate_directions(directions: np.ndarray, degrees: float) -> np.ndarray:
    """Return directions rotated by ``degrees`` (positive = clockwise add)."""
    return wrap_degrees(np.asarray(directions, dtype=float) + float(degrees))
