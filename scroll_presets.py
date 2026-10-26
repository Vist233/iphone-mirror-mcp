"""Shared public scroll presets; values are per-event input deltas."""

SCROLL_MAGNITUDES = (20, 50, 100, 200)
DEFAULT_SCROLL_MAGNITUDE = 50
SIGNED_SCROLL_DELTAS = tuple(sorted(value * sign for value in SCROLL_MAGNITUDES for sign in (-1, 1)))
