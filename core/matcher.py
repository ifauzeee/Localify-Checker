from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd
from rapidfuzz import fuzz, process

from core.normalizer import (
    display_title_from_filename,
    guess_artist_from_folder,
    normalize_artist,
    normalize_title,
)


ProgressCallback = Callable[[int, str], None]


@dataclass(frozen=True)
class MatchConfig:
    match_threshold: int = 92
    possible_threshold: int = 75


def _prepare_local(local_df: pd.DataFrame) -> pd.DataFrame:
    prepared = local_df.copy()
    prepared["local_title"] = prepared["filename"].map(display_title_from_filename)
    prepared["local_artist"] = prepared["folder"].map(guess_artist_from_folder)
    prepared["normalized_title"] = prepared["filename"].map(normalize_title)
    prepared["normalized_artist"] = prepared["local_artist"].map(normalize_artist)
    prepared = prepared[prepared["normalized_title"].ne("")]
    prepared = prepared.reset_index(drop=True)
    return prepared


def _score_candidate(
    spotify_title_norm: str,
    spotify_artist_norm: str,
    local_title_norm: str,
    local_artist_norm: str,
) -> int:
    if spotify_title_norm == local_title_norm:
        title_score = 100.0
    else:
        spotify_tokens = set(spotify_title_norm.split())
        local_tokens = set(local_title_norm.split())
        shared_tokens = spotify_tokens & local_tokens
        min_token_count = max(1, min(len(spotify_tokens), len(local_tokens)))
        union_token_count = max(1, len(spotify_tokens | local_tokens))
        overlap = len(shared_tokens) / min_token_count
        jaccard = len(shared_tokens) / union_token_count

        direct_score = fuzz.ratio(spotify_title_norm, local_title_norm)
        sorted_score = fuzz.token_sort_ratio(spotify_title_norm, local_title_norm)
        set_score = fuzz.token_set_ratio(spotify_title_norm, local_title_norm)
        partial_score = fuzz.partial_ratio(spotify_title_norm, local_title_norm)

        title_score = max(direct_score, sorted_score)
        if overlap >= 0.8 and jaccard >= 0.55:
            title_score = max(title_score, set_score)
        if overlap >= 0.85 and partial_score >= 95:
            title_score = max(title_score, min(partial_score, 90))

    if spotify_artist_norm and local_artist_norm:
        artist_score = fuzz.token_set_ratio(spotify_artist_norm, local_artist_norm)
        if artist_score >= 90 and title_score >= 70:
            title_score = min(100, title_score + 5)
        elif artist_score < 55 and title_score < 96:
            title_score = max(0, title_score - 5)

    return int(round(title_score))


def match_tracks(
    spotify_df: pd.DataFrame,
    local_df: pd.DataFrame,
    config: MatchConfig | None = None,
    progress_callback: ProgressCallback | None = None,
) -> pd.DataFrame:
    config = config or MatchConfig()
    local_prepared = _prepare_local(local_df)

    choices = {
        index: title
        for index, title in local_prepared["normalized_title"].items()
        if isinstance(title, str) and title
    }

    rows: list[dict[str, object]] = []
    total = len(spotify_df)

    for position, (_index, spotify_row) in enumerate(spotify_df.iterrows(), start=1):
        spotify_song = str(spotify_row.get("track_name", "")).strip()
        spotify_artist = str(spotify_row.get("artist", "")).strip()
        spotify_title_norm = normalize_title(spotify_song)
        spotify_artist_norm = normalize_artist(spotify_artist)

        best_local = None
        best_score = 0

        if spotify_title_norm and choices:
            candidates = process.extract(
                spotify_title_norm,
                choices,
                scorer=fuzz.token_sort_ratio,
                limit=12,
            )
            for _match_text, _raw_score, local_index in candidates:
                local_row = local_prepared.loc[local_index]
                score = _score_candidate(
                    spotify_title_norm,
                    spotify_artist_norm,
                    str(local_row["normalized_title"]),
                    str(local_row["normalized_artist"]),
                )
                if score > best_score:
                    best_score = score
                    best_local = local_row

        if best_score >= config.match_threshold:
            status = "MATCH"
        elif best_score >= config.possible_threshold:
            status = "POSSIBLE MATCH"
        else:
            status = "MISSING"
            best_local = None

        rows.append(
            {
                "Spotify Song": spotify_song,
                "Artist": spotify_artist,
                "Local Match": "" if best_local is None else str(best_local["local_title"]),
                "Folder": "" if best_local is None else str(best_local["folder"]),
                "Status": status,
                "Similarity Score": best_score,
            }
        )

        if progress_callback and total:
            progress = 30 + int((position / total) * 60)
            progress_callback(min(progress, 90), f"Matching {position} of {total}")

    return pd.DataFrame(
        rows,
        columns=[
            "Spotify Song",
            "Artist",
            "Local Match",
            "Folder",
            "Status",
            "Similarity Score",
        ],
    )


def summarize_results(report_df: pd.DataFrame, local_count: int) -> dict[str, float | int]:
    total_spotify = len(report_df)
    match_count = int((report_df["Status"] == "MATCH").sum()) if total_spotify else 0
    possible_count = int((report_df["Status"] == "POSSIBLE MATCH").sum()) if total_spotify else 0
    missing_count = int((report_df["Status"] == "MISSING").sum()) if total_spotify else 0
    completeness = (match_count / total_spotify * 100) if total_spotify else 0

    return {
        "total_spotify": total_spotify,
        "total_local": int(local_count),
        "match": match_count,
        "possible_match": possible_count,
        "missing": missing_count,
        "completeness": round(completeness, 2),
    }
