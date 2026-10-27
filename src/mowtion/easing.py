"""Calm motion curves. Springs settle; nothing flashes or shakes."""

from __future__ import annotations

import math


def clamp(x: float, a: float = 0.0, b: float = 1.0) -> float:
    return a if x < a else b if x > b else x


def lerp(a: float, b: float, p: float) -> float:
    return a + (b - a) * p


def ease_out(x: float) -> float:
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_in_out(x: float) -> float:
    """Smoothstep. Used for fades, wipes, and iris opens."""
    x = clamp(x)
    return x * x * (3 - 2 * x)


def spring(t: float, w: float = 9.0, z: float = 0.78) -> float:
    """Damped spring step. ``t`` is seconds since the motion started.

    Zeta stays high on purpose so the overshoot is a soft settle, not a shake.
    """
    if t <= 0:
        return 0.0
    if z >= 1:
        return 1 - (1 + w * t) * math.exp(-w * t)
    wd = w * math.sqrt(1 - z * z)
    return 1 - math.exp(-z * w * t) * (math.cos(wd * t) + (z * w / wd) * math.sin(wd * t))


def container_open(local_t: float) -> float:
    """Box / frame progress. Starts almost immediately."""
    return clamp(spring(local_t - 0.04, 8.5, 0.8))


def text_open(local_t: float) -> float:
    """Lettering progress. Trails the container by about a fifth of a second."""
    return clamp(spring(local_t - 0.22, 9.0, 0.82))


def leading(local_t: float, dur: float = 0.9) -> float:
    """0 at the start of a stroke, 1 when the stroke has reached its end.

    Callers draw from the origin toward the far point, so the leading edge
    arrives first and the rest of the mark fills in behind it.
    """
    if dur <= 0:
        return 1.0
    return ease_in_out(local_t / dur)
