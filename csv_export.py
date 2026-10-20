"""Export path lists to CSV."""

from __future__ import annotations

import csv
from pathlib import Path


def save_paths_csv(paths: list[Path], csv_path: Path) -> None:
    """
    Write one column CSV of absolute path strings.

    Args:
        paths: File paths to export.
        csv_path: Output file (parent directories are created).
    """
    csv_path = csv_path.resolve()
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["absolute_path"])
        for path in paths:
            writer.writerow([str(path.resolve())])
