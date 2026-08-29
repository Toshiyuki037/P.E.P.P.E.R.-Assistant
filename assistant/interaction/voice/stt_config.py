"""
P.E.P.P.E.R. - English Speech Recognition Configuration

Phase 14

Purpose:
    Centralizes P.E.P.P.E.R.'s production English-only STT configuration.

The live voice runtime uses an English-only Distil-Whisper model and
explicit English decoding. Partial recognition remains lightweight while
the authoritative final pass uses stronger beam search.
"""

# Strong English-only CTranslate2 checkpoint.
WHISPER_MODEL_NAME = (
    "distil-whisper/"
    "distil-large-v3.5-ct2"
)

WHISPER_LANGUAGE = "en"

# Keep partials responsive. They are observational only.
PARTIAL_BEAM_SIZE = 1

# Spend more decoding work on the transcript that actually enters P.E.P.P.E.R.
FINAL_BEAM_SIZE = 5

# Prevent cross-window text conditioning from dragging an earlier recognition
# mistake through the rest of the utterance.
CONDITION_ON_PREVIOUS_TEXT = False

# P.E.P.P.E.R. already owns the speech boundary with assistant.interaction.voice.vad.
WHISPER_VAD_FILTER = False

# Project/domain vocabulary hints. These are hints, not forced replacements.
WHISPER_HOTWORDS = (
    "P.E.P.P.E.R. EV E.V. Max "
    "electrical engineering embedded systems "
    "transistor transistors resistor resistors "
    "logic gate logic gates FPGA HDL Verilog VHDL "
    "microcontroller semiconductor semiconductors "
    "Raspberry Pi CUDA GPU CPU memory "
    "Oregon State Corvallis"
)
