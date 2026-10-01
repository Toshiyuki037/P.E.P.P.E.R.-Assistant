# P.E.P.P.E.R. Visual HUD

## Included
- `hud.py` — transparent Windows HUD host + adaptive text contrast + standalone demo.
- `hud.html` — exact displayed text and the SiriWave iOS 9 renderer.
- `audio_meter.py` — helper for converting real PCM16 TTS chunks into a 0..1 waveform level.
- `vendor/siriwave.umd.min.js` — the SiriWave bundle you supplied.
- `requirements.txt`.

## One font file you must add
Copy your medium SF Pro Display font here and name it exactly:

`pepper_hud/SFPRODISPLAYMEDIUM.OTF`

Use **Medium (500)** for the response text. It is slightly heavier than Regular without looking bold.

The font is intentionally not redistributed in this package.

## Install / run
From the `pepper-assistant` root:

```powershell
python -m pip install -r pepper_hud\requirements.txt
python pepper_hud\hud.py
```

The standalone test starts automatically. Keys: `1–5`, `Space`, `A`, `L`, `D`, `Esc`.

## Real TTS integration
The standalone demo generates a fake audio envelope only to certify the UI. In production:

```python
from pepper_hud.hud import PepperHUD
from pepper_hud.audio_meter import pcm16_rms_level

hud.speak(spoken_text)

for pcm_chunk in tts_pcm_chunks:
    play_audio(pcm_chunk)
    hud.set_audio_level(pcm16_rms_level(pcm_chunk))

hud.finish_speech()
```

The important rule is: pass the same `spoken_text` string to TTS and to `hud.speak()`. The HUD does not generate or modify assistant text.

If your TTS layer exposes float samples rather than PCM16 bytes, compute its RMS directly and feed a normalized `0..1` value to `hud.set_audio_level()`.

## Files to keep in the final assistant
All five runtime files are local:
- `hud.py`
- `hud.html`
- `audio_meter.py`
- `SFPRODISPLAYMEDIUM.OTF`
- `vendor/siriwave.umd.min.js`

No npm process or internet connection is required at runtime.


## V2 visual tuning
V2 increases the overlay to 500×220, the SiriWave canvas to 500×118, and vertically scales the wave slightly so the fluorescent iOS9 curves are clearly visible in a screen recording. It also reveals the response character-by-character over the same speech-duration clock. For real integration, call `set_audio_level()` continuously from actual TTS PCM and `finish_speech()` when playback ends.
