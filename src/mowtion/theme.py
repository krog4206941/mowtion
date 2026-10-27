"""Selectable look presets. Colors only — motion rules are shared."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Theme:
    id: str
    name: str
    tagline: str
    bg: str
    bg2: str
    panel: str
    ink: str
    muted: str
    line: str
    accent: str
    accent2: str
    on_accent: str
    mood: str  # music mood key
    bpm: int

    def to_dict(self) -> dict:
        return asdict(self)


PRESETS: dict[str, Theme] = {
    "dark-techy": Theme(
        id="dark-techy",
        name="Dark Techy",
        tagline="Navy, teal, and a little gold.",
        bg="#07090C",
        bg2="#121A24",
        panel="#141C27",
        ink="#E8E4DA",
        muted="#8A93A0",
        line="#2A3848",
        accent="#4FD1E0",
        accent2="#CCA75E",
        on_accent="#071016",
        mood="minor",
        bpm=90,
    ),
    "clean-light": Theme(
        id="clean-light",
        name="Clean Light",
        tagline="Warm paper, ink, and crimson.",
        bg="#EDEDE8",
        bg2="#F7F4EF",
        panel="#F9F9F6",
        ink="#121713",
        muted="#8C8E88",
        line="#E4E3DD",
        accent="#D7043B",
        accent2="#121713",
        on_accent="#FFFFFF",
        mood="major",
        bpm=96,
    ),
    "warm-editorial": Theme(
        id="warm-editorial",
        name="Warm Editorial",
        tagline="Clay paper and terracotta.",
        bg="#F3E6D4",
        bg2="#EAD8C4",
        panel="#FFF8F0",
        ink="#2A2118",
        muted="#8A7564",
        line="#E6D4C2",
        accent="#C4552A",
        accent2="#1F6B5A",
        on_accent="#FFF8F0",
        mood="warm",
        bpm=84,
    ),
    "midnight-neon": Theme(
        id="midnight-neon",
        name="Midnight Neon",
        tagline="Violet night and a lime edge.",
        bg="#0C0716",
        bg2="#1A0E2A",
        panel="#160E24",
        ink="#F4EEFF",
        muted="#A394B8",
        line="#2C2140",
        accent="#D6FF4A",
        accent2="#B388FF",
        on_accent="#140C1E",
        mood="pulse",
        bpm=100,
    ),
    "studio-blue": Theme(
        id="studio-blue",
        name="Studio Blue",
        tagline="Daylight blue and a gold tick.",
        bg="#E7EEF6",
        bg2="#F7F9FC",
        panel="#FFFFFF",
        ink="#102033",
        muted="#6D7C90",
        line="#D5E0EC",
        accent="#1F6FEB",
        accent2="#E8A317",
        on_accent="#FFFFFF",
        mood="airy",
        bpm=94,
    ),
}


def get_theme(preset_id: str) -> Theme:
    key = (preset_id or "").strip().lower()
    if key not in PRESETS:
        known = ", ".join(PRESETS)
        raise KeyError(f"Unknown preset {preset_id!r}. Choose one of: {known}")
    return PRESETS[key]


def list_themes() -> list[dict]:
    return [theme.to_dict() for theme in PRESETS.values()]
