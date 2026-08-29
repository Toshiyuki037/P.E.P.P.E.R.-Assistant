"""
P.E.P.P.E.R. - ECAPA Owner Voice Verification

Purpose:
    Verify a captured 16 kHz microphone utterance against the enrolled
    ECAPA owner profile BEFORE the utterance reaches final Whisper STT.

Architecture:
    microphone -> existing VAD/capture -> ECAPA owner gate -> Whisper

This module does not own:
    - wake detection
    - sensitive-action authorization
    - reasoning
    - tools
    - TTS
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import numpy as np
import torch

from speechbrain.inference.speaker import SpeakerRecognition


ROOT = Path(__file__).resolve().parents[3]

MODEL_SOURCE = (
    "speechbrain/spkrec-ecapa-voxceleb"
)

MODEL_DIR = (
    ROOT
    / "runtime"
    / "models"
    / "spkrec-ecapa-voxceleb"
)

OWNER_EMBEDDING_PATH = (
    ROOT
    / "runtime"
    / "voice_identity"
    / "owner_ecapa.npy"
)

CALIBRATION_PATH = (
    ROOT
    / "runtime"
    / "voice_identity"
    / "ecapa_calibration.json"
)

DEFAULT_THRESHOLD = 0.40
MINIMUM_AUDIO_SECONDS = 0.30

_MODEL_LOCK = threading.RLock()
_MODEL = None
_OWNER_EMBEDDING = None
_THRESHOLD = None


class OwnerVerificationResult:
    def __init__(
        self,
        *,
        matched: bool,
        similarity: float,
        threshold: float,
        elapsed_seconds: float,
        reason: str = "",
    ):
        self.matched = bool(
            matched
        )

        self.similarity = float(
            similarity
        )

        self.threshold = float(
            threshold
        )

        self.elapsed_seconds = float(
            elapsed_seconds
        )

        self.reason = str(
            reason
            or ""
        )


def _normalize(
    vector,
):
    vector = np.asarray(
        vector,
        dtype=np.float32,
    ).reshape(
        -1
    )

    norm = float(
        np.linalg.norm(
            vector
        )
        or 1.0
    )

    return (
        vector
        / norm
    )


def _load_threshold():
    override = (
        os.getenv(
            "EVIE_OWNER_THRESHOLD",
            "",
        )
        .strip()
    )

    if override:

        try:

            return float(
                override
            )

        except ValueError:

            pass

    if CALIBRATION_PATH.exists():

        try:

            data = json.loads(
                CALIBRATION_PATH.read_text(
                    encoding=
                        "utf-8"
                )
            )

            recommended = data.get(
                "recommended_threshold"
            )

            if recommended is not None:

                # Start slightly above the measured midpoint while remaining
                # well below the observed fresh-owner floor.
                return max(
                    0.50,
                    float(
                        recommended
                    ),
                )

        except Exception:

            pass

    return float(
        DEFAULT_THRESHOLD
    )


def _load_owner_embedding():
    if not OWNER_EMBEDDING_PATH.exists():

        raise FileNotFoundError(
            (
                "ECAPA owner profile not found: "
                f"{OWNER_EMBEDDING_PATH}"
            )
        )

    return _normalize(
        np.load(
            str(
                OWNER_EMBEDDING_PATH
            )
        )
    )


def _get_model():
    global _MODEL
    global _OWNER_EMBEDDING
    global _THRESHOLD

    if _MODEL is not None:

        return (
            _MODEL,
            _OWNER_EMBEDDING,
            _THRESHOLD,
        )

    with _MODEL_LOCK:

        if _MODEL is None:

            # Keep ECAPA on CPU so speaker verification does not contend with
            # Whisper/Lux/reasoning GPU workloads. The model remains resident
            # after first use.
            print(
                "Loading P.E.P.P.E.R. ECAPA owner verifier..."
            )

            _MODEL = (
                SpeakerRecognition.from_hparams(
                    source=
                        MODEL_SOURCE,
                    savedir=
                        str(
                            MODEL_DIR
                        ),
                    run_opts=
                        {
                            "device":
                                "cpu",
                        },
                )
            )

            _OWNER_EMBEDDING = (
                _load_owner_embedding()
            )

            _THRESHOLD = (
                _load_threshold()
            )

            print(
                (
                    "P.E.P.P.E.R. ECAPA owner verifier ready. "
                    f"threshold={_THRESHOLD:.4f}"
                )
            )

    return (
        _MODEL,
        _OWNER_EMBEDDING,
        _THRESHOLD,
    )


def _embedding_from_audio(
    verifier,
    audio,
):
    waveform = torch.from_numpy(
        np.asarray(
            audio,
            dtype=np.float32,
        )
    ).reshape(
        1,
        -1,
    )

    lengths = torch.ones(
        waveform.shape[
            0
        ],
        dtype=
            torch.float32,
    )

    with torch.inference_mode():

        embedding = (
            verifier.encode_batch(
                waveform,
                wav_lens=
                    lengths,
                normalize=
                    True,
            )
        )

    return _normalize(
        embedding
        .detach()
        .float()
        .cpu()
        .numpy()
        .reshape(
            -1
        )
    )


def verify_owner_audio(
    audio,
    sample_rate: int,
):
    started = (
        time.monotonic()
    )

    sample_rate = int(
        sample_rate
    )

    audio = np.asarray(
        audio,
        dtype=np.float32,
    ).reshape(
        -1
    )

    if (
        sample_rate <= 0
        or audio.size == 0
    ):

        return OwnerVerificationResult(
            matched=False,
            similarity=0.0,
            threshold=
                _load_threshold(),
            elapsed_seconds=
                time.monotonic()
                - started,
            reason=
                "empty_audio",
        )

    duration = (
        audio.size
        / float(
            sample_rate
        )
    )

    if duration < MINIMUM_AUDIO_SECONDS:

        return OwnerVerificationResult(
            matched=False,
            similarity=0.0,
            threshold=
                _load_threshold(),
            elapsed_seconds=
                time.monotonic()
                - started,
            reason=
                "audio_too_short",
        )

    # Current P.E.P.P.E.R. STT capture is already 16 kHz. Do not silently resample
    # unexpected formats inside the identity gate.
    if sample_rate != 16000:

        return OwnerVerificationResult(
            matched=False,
            similarity=0.0,
            threshold=
                _load_threshold(),
            elapsed_seconds=
                time.monotonic()
                - started,
            reason=
                (
                    "unsupported_sample_rate_"
                    f"{sample_rate}"
                ),
        )

    # listen.py supplies int16 microphone PCM. Normalize to SpeechBrain's
    # expected floating waveform range.
    peak = float(
        np.max(
            np.abs(
                audio
            )
        )
        or 0.0
    )

    if peak > 1.5:

        audio = (
            audio
            / 32768.0
        )

    verifier, owner_embedding, threshold = (
        _get_model()
    )

    with _MODEL_LOCK:

        current_embedding = (
            _embedding_from_audio(
                verifier,
                audio,
            )
        )

    similarity = float(
        np.dot(
            current_embedding,
            owner_embedding,
        )
    )

    return OwnerVerificationResult(
        matched=(
            similarity
            >= float(
                threshold
            )
        ),
        similarity=
            similarity,
        threshold=
            threshold,
        elapsed_seconds=
            time.monotonic()
            - started,
        reason=
            "matched"
            if similarity
            >= threshold
            else "speaker_mismatch",
    )


def prewarm_owner_verifier():
    """
    Optional startup/background prewarm hook.
    """
    _get_model()
