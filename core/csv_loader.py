from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import pandas as pd


class CsvSchemaError(ValueError):
    """Raised when an imported CSV does not contain the expected columns."""


def _read_csv(path: str | Path) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    encodings = ("utf-8-sig", "utf-8", "cp1252", "latin1")
    last_error: Exception | None = None

    for encoding in encodings:
        try:
            return pd.read_csv(
                csv_path,
                dtype=str,
                keep_default_na=False,
                sep=None,
                engine="python",
                encoding=encoding,
            )
        except UnicodeDecodeError as exc:
            last_error = exc
        except pd.errors.ParserError as exc:
            last_error = exc

    if last_error:
        raise CsvSchemaError(f"Could not read CSV: {last_error}") from last_error
    raise CsvSchemaError("Could not read CSV file.")


def _canonical_column(name: str) -> str:
    lowered = name.strip().lower()
    lowered = re.sub(r"[^a-z0-9]+", "_", lowered)
    return lowered.strip("_")


def _find_column(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    original_by_key = {_canonical_column(column): column for column in columns}
    candidate_keys = [_canonical_column(candidate) for candidate in candidates]

    for candidate in candidate_keys:
        if candidate in original_by_key:
            return original_by_key[candidate]

    for key, original in original_by_key.items():
        if any(candidate in key for candidate in candidate_keys):
            return original

    return None


def load_local_csv(path: str | Path) -> pd.DataFrame:
    df = _read_csv(path)

    folder_col = _find_column(df.columns, ("folder", "directory", "path", "album_folder"))
    filename_col = _find_column(
        df.columns,
        ("filename", "file_name", "file", "name", "title"),
    )

    if not folder_col or not filename_col:
        raise CsvSchemaError(
            "CSV musik lokal harus memiliki kolom folder dan filename. "
            f"Kolom yang ditemukan: {', '.join(map(str, df.columns))}"
        )

    local_df = pd.DataFrame(
        {
            "folder": df[folder_col].astype(str).str.strip(),
            "filename": df[filename_col].astype(str).str.strip(),
        }
    )
    local_df = local_df[local_df["filename"].ne("")]
    local_df = local_df.reset_index(drop=True)
    return local_df


def load_spotify_csv(path: str | Path) -> pd.DataFrame:
    df = _read_csv(path)

    track_col = _find_column(
        df.columns,
        (
            "track_name",
            "track name",
            "track",
            "song_name",
            "song name",
            "song",
            "title",
            "name",
        ),
    )
    artist_col = _find_column(
        df.columns,
        (
            "artist_name",
            "artist name",
            "artist",
            "artists",
            "main_artist",
            "album_artist",
            "creator",
        ),
    )
    album_col = _find_column(
        df.columns,
        ("album", "album_name", "album name", "release", "collection"),
    )

    if not track_col:
        raise CsvSchemaError(
            "CSV Spotify harus memiliki kolom nama lagu, misalnya track_name, "
            "Track name, song, title, atau name. "
            f"Kolom yang ditemukan: {', '.join(map(str, df.columns))}"
        )

    spotify_df = pd.DataFrame(
        {
            "track_name": df[track_col].astype(str).str.strip(),
            "artist": df[artist_col].astype(str).str.strip() if artist_col else "",
            "album": df[album_col].astype(str).str.strip() if album_col else "",
        }
    )
    spotify_df = spotify_df[spotify_df["track_name"].ne("")]
    spotify_df = spotify_df.reset_index(drop=True)
    return spotify_df

