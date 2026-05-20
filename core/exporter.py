from __future__ import annotations

from pathlib import Path

import pandas as pd


def export_reports(report_df: pd.DataFrame, output_dir: str | Path) -> dict[str, Path]:
    if report_df.empty:
        raise ValueError("Tidak ada hasil analisis untuk diexport.")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    files = {
        "full_report": output_path / "full_report.csv",
        "matched": output_path / "matched.csv",
        "missing": output_path / "missing.csv",
        "possible_match": output_path / "possible_match.csv",
    }

    report_df.to_csv(files["full_report"], index=False, encoding="utf-8-sig")
    report_df[report_df["Status"] == "MATCH"].to_csv(
        files["matched"], index=False, encoding="utf-8-sig"
    )
    report_df[report_df["Status"] == "MISSING"].to_csv(
        files["missing"], index=False, encoding="utf-8-sig"
    )
    report_df[report_df["Status"] == "POSSIBLE MATCH"].to_csv(
        files["possible_match"], index=False, encoding="utf-8-sig"
    )

    return files

