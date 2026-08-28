from __future__ import annotations

import base64
import json
import sys
import traceback
from pathlib import Path

import numpy as np
import torch

from zipvoice.luxvoice import LuxTTS


PROJECT_ROOT = Path(__file__).resolve().parents[2]

REF_AUDIO = (
    PROJECT_ROOT
    / "pepper-voice"
    / "references"
    / "pepper-reference.wav"
)

SAMPLE_RATE = 48000

NUM_STEPS = 4
GUIDANCE_SCALE = 1.5
REFERENCE_RMS = 0.01
VOICE_SPEED = 0.97
END_SILENCE_SECONDS = 0.15
SEED = 42


def _protocol(payload):
    sys.stdout.write(
        json.dumps(
            payload,
            separators=(",", ":"),
        )
        + "\n"
    )
    sys.stdout.flush()


class _StdoutToStderr:
    def write(self, value):
        sys.stderr.write(str(value))
        sys.stderr.flush()

    def flush(self):
        sys.stderr.flush()


def _slow_audio(audio: np.ndarray, speed: float) -> np.ndarray:
    audio = np.asarray(
        audio,
        dtype=np.float32,
    ).reshape(-1)

    speed = float(speed)

    if (
        audio.size < 2
        or speed <= 0.0
        or abs(speed - 1.0) < 1e-6
    ):
        return audio

    output_length = max(
        1,
        int(
            round(
                audio.size
                / speed
            )
        ),
    )

    old_positions = np.linspace(
        0.0,
        1.0,
        num=audio.size,
        endpoint=True,
        dtype=np.float64,
    )

    new_positions = np.linspace(
        0.0,
        1.0,
        num=output_length,
        endpoint=True,
        dtype=np.float64,
    )

    return np.interp(
        new_positions,
        old_positions,
        audio,
    ).astype(
        np.float32,
        copy=False,
    )


def _append_end_silence(
    audio: np.ndarray,
    seconds: float,
) -> np.ndarray:
    frames = max(
        0,
        int(
            round(
                float(seconds)
                * SAMPLE_RATE
            )
        ),
    )

    if frames <= 0:
        return audio

    return np.concatenate(
        (
            np.asarray(
                audio,
                dtype=np.float32,
            ),
            np.zeros(
                frames,
                dtype=np.float32,
            ),
        )
    )


def _load():
    if not REF_AUDIO.exists():
        raise FileNotFoundError(
            f"P.E.P.P.E.R. reference audio not found: {REF_AUDIO}"
        )

    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA unavailable. P.E.P.P.E.R. LuxTTS production worker requires CUDA."
        )

    print(
        "[LuxTTS] GPU:",
        torch.cuda.get_device_name(0),
        file=sys.stderr,
        flush=True,
    )

    print(
        "[LuxTTS] Loading model...",
        file=sys.stderr,
        flush=True,
    )

    original_stdout = sys.stdout

    try:
        sys.stdout = _StdoutToStderr()

        tts = LuxTTS(
            "YatharthS/LuxTTS",
            device="cuda",
        )

        print(
            "[LuxTTS] Encoding P.E.P.P.E.R. reference...",
            file=sys.stderr,
            flush=True,
        )

        prompt = tts.encode_prompt(
            str(
                REF_AUDIO
            ),
            rms=REFERENCE_RMS,
        )

        print(
            "[LuxTTS] Warming GPU...",
            file=sys.stderr,
            flush=True,
        )

        torch.manual_seed(999)
        torch.cuda.manual_seed_all(999)

        _ = tts.generate_speech(
            "Ready.",
            prompt,
            num_steps=NUM_STEPS,
            guidance_scale=GUIDANCE_SCALE,
        )

        torch.cuda.synchronize()

    finally:
        sys.stdout = original_stdout

    print(
        (
            "[LuxTTS] Ready. "
            f"speed={VOICE_SPEED}, "
            f"end_silence={END_SILENCE_SECONDS:.2f}s"
        ),
        file=sys.stderr,
        flush=True,
    )

    return tts, prompt


def _synthesize(
    tts,
    prompt,
    text: str,
) -> np.ndarray:
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)

    original_stdout = sys.stdout

    try:
        sys.stdout = _StdoutToStderr()

        wav = tts.generate_speech(
            text,
            prompt,
            num_steps=NUM_STEPS,
            guidance_scale=GUIDANCE_SCALE,
        )

        torch.cuda.synchronize()

    finally:
        sys.stdout = original_stdout

    audio = (
        wav.detach()
        .float()
        .cpu()
        .numpy()
        .squeeze()
        .astype(
            np.float32,
            copy=False,
        )
    )

    audio = _slow_audio(
        audio,
        VOICE_SPEED,
    )

    audio = _append_end_silence(
        audio,
        END_SILENCE_SECONDS,
    )

    return audio


def main():
    try:
        tts, prompt = _load()

    except Exception as error:
        _protocol(
            {
                "type": "error",
                "error": (
                    "LuxTTS initialization failed: "
                    f"{error}"
                ),
            }
        )

        traceback.print_exc(
            file=sys.stderr
        )

        return 1

    _protocol(
        {
            "type": "ready",
            "sample_rate": SAMPLE_RATE,
        }
    )

    for raw_line in sys.stdin:
        raw_line = raw_line.strip()

        if not raw_line:
            continue

        try:
            request = json.loads(
                raw_line
            )

            command = request.get(
                "command"
            )

            if command == "shutdown":
                break

            if command != "synthesize":
                raise ValueError(
                    f"Unknown command: {command!r}"
                )

            text = str(
                request.get(
                    "text",
                    "",
                )
                or ""
            ).strip()

            if not text:
                _protocol(
                    {
                        "type": "audio",
                        "sample_rate": SAMPLE_RATE,
                        "audio": "",
                    }
                )

                continue

            audio = _synthesize(
                tts,
                prompt,
                text,
            )

            encoded = base64.b64encode(
                np.asarray(
                    audio,
                    dtype=np.float32,
                ).tobytes()
            ).decode(
                "ascii"
            )

            _protocol(
                {
                    "type": "audio",
                    "sample_rate": SAMPLE_RATE,
                    "audio": encoded,
                }
            )

        except Exception as error:
            _protocol(
                {
                    "type": "error",
                    "error": str(
                        error
                    ),
                }
            )

            traceback.print_exc(
                file=sys.stderr
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
