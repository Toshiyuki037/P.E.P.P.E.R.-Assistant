"""Tiny helper for driving the HUD from real TTS PCM audio."""
from __future__ import annotations
import math
from array import array

def pcm16_rms_level(pcm_bytes: bytes, gain: float = 3.2) -> float:
    """Convert little-endian signed PCM16 bytes to a normalized 0..1 visual level."""
    if not pcm_bytes:
        return 0.0
    samples = array("h")
    samples.frombytes(pcm_bytes)
    if not samples:
        return 0.0
    # Windows/x86 is little-endian; swap if ever run on big-endian hardware.
    if __import__("sys").byteorder != "little":
        samples.byteswap()
    mean_square = sum(float(s) * float(s) for s in samples) / len(samples)
    rms = math.sqrt(mean_square) / 32768.0
    # sqrt compression makes normal speech visually responsive without clipping constantly.
    return max(0.0, min(1.0, math.sqrt(rms) * gain))
