from __future__ import annotations

import re
import unicodedata
from pathlib import Path


AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav", ".m4a", ".ogg"}

NOISE_PATTERNS = (
    r"\bofficial\s+audio\b",
    r"\bofficial\s+video\b",
    r"\blyric\s+video\b",
    r"\blyrics?\b",
    r"\bremaster(?:ed)?(?:\s+\d{4})?\b",
    r"\bexplicit\b",
    r"\bclean\b",
    r"\bmusic\s+video\b",
    r"\bvisualizer\b",
)


def strip_audio_extension(value: str) -> str:
    text = str(value or "").strip()
    suffix = Path(text).suffix.lower()
    if suffix in AUDIO_EXTENSIONS:
        return str(Path(text).with_suffix(""))
    return re.sub(r"\.(?:mp3|flac|wav|m4a|ogg)$", "", text, flags=re.IGNORECASE)


def normalize_text(value: str, *, remove_feat_tail: bool = False) -> str:
    text = strip_audio_extension(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower()
    text = re.sub(r"^\s*\d{1,3}\s*[\.\-_\)]\s*", " ", text)
    text = re.sub(r"^\s*0\d\s+(?=\D)", " ", text)

    text = re.sub(
        r"[\(\[\{][^\)\]\}]*\b(?:feat\.?|ft\.?|featuring)\b[^\)\]\}]*[\)\]\}]",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    if remove_feat_tail:
        text = re.sub(r"\b(?:feat\.?|ft\.?|featuring)\b.*$", " ", text, flags=re.IGNORECASE)
    else:
        text = re.sub(r"\b(?:feat\.?|ft\.?|featuring)\b", " ", text, flags=re.IGNORECASE)

    for pattern in NOISE_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

    text = text.replace("&", " and ")
    text = re.sub(r"[-_()\[\]{}.,!?'\"`~:;|/\\]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_title(value: str) -> str:
    return normalize_text(value, remove_feat_tail=True)


def normalize_artist(value: str) -> str:
    return normalize_text(value, remove_feat_tail=False)


def display_title_from_filename(filename: str) -> str:
    return strip_audio_extension(filename).strip()


def guess_artist_from_folder(folder: str) -> str:
    parts = re.split(r"[\\/]+", str(folder or ""))
    for part in parts:
        cleaned = part.strip()
        if cleaned:
            return cleaned
    return ""
