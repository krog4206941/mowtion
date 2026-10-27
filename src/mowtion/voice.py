"""Kokoro TTS. Default voice is an even blend of am_michael and am_onyx at 1.03×."""

from __future__ import annotations

import numpy as np

DEFAULT_BLEND = {"am_michael": 0.5, "am_onyx": 0.5}
DEFAULT_SPEED = 1.03
DEFAULT_LANG = "en-us"


def blend_style(kokoro, weights: dict[str, float] | None = None):
    weights = weights or DEFAULT_BLEND
    total = float(sum(weights.values())) or 1.0
    style = None
    for name, weight in weights.items():
        piece = kokoro.get_voice_style(name) * (float(weight) / total)
        style = piece if style is None else style + piece
    return style


def synthesize(
    text: str,
    *,
    speed: float = DEFAULT_SPEED,
    lang: str = DEFAULT_LANG,
    blend: dict[str, float] | None = None,
    phoneme_fix: dict[str, str] | None = None,
    progress=None,
) -> tuple[np.ndarray, int]:
    """Speak ``text``. Returns float32 mono samples and the sample rate (24 kHz)."""
    from mowtion.models import load_kokoro

    kokoro = load_kokoro(progress)
    style = blend_style(kokoro, blend)
    spoken = text.strip()
    if not spoken:
        raise ValueError("The script is empty.")
    if phoneme_fix:
        phonemes = kokoro.tokenizer.phonemize(spoken, lang)
        for src, dst in phoneme_fix.items():
            phonemes = phonemes.replace(src, dst)
        audio, sr = kokoro.create(
            phonemes,
            voice=style,
            speed=speed,
            lang=lang,
            is_phonemes=True,
            trim=True,
        )
    else:
        audio, sr = kokoro.create(spoken, voice=style, speed=speed, lang=lang, trim=True)
    audio = np.asarray(audio, dtype=np.float32)
    peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
    if peak > 0:
        audio = audio / peak * 0.8
    return audio, int(sr)
