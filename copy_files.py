"""Copy files with progress reporting."""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

ShouldCancel = Callable[[], bool]


@dataclass(frozen=True)
class CopyProgress:
    """Snapshot of copy operation progress."""

    total: int
    copied: int
    skipped: int
    failed: int
    current_name: str
    percent: float


ProgressCallback = Callable[[CopyProgress], None]


def filter_sources_not_in_dest(
    sources: list[Path],
    dest_dir: Path,
) -> tuple[list[Path], list[Path]]:
    """
    Split sources by whether their file name already exists in ``dest_dir``.

    Args:
        sources: Candidate files to copy.
        dest_dir: Destination folder (need not exist yet).

    Returns:
        Tuple of (to_copy, already_present).
    """
    dest = dest_dir.resolve()
    if not dest.is_dir():
        return list(sources), []

    to_copy: list[Path] = []
    already_present: list[Path] = []
    for source in sources:
        if (dest / source.name).exists():
            already_present.append(source)
        else:
            to_copy.append(source)
    return to_copy, already_present


def _emit(
    callback: Optional[ProgressCallback],
    total: int,
    copied: int,
    skipped: int,
    failed: int,
    current_name: str,
) -> None:
    if callback is None:
        return
    done = copied + skipped + failed
    percent = (done / total * 100.0) if total else 100.0
    callback(
        CopyProgress(
            total=total,
            copied=copied,
            skipped=skipped,
            failed=failed,
            current_name=current_name,
            percent=percent,
        )
    )


def _maybe_emit(
    callback: Optional[ProgressCallback],
    total: int,
    copied: int,
    skipped: int,
    failed: int,
    current_name: str,
    *,
    force: bool,
    progress_every: int,
) -> None:
    if not force:
        done = copied + skipped + failed
        if progress_every > 1 and done % progress_every != 0:
            return
    _emit(callback, total, copied, skipped, failed, current_name)


def copy_file_list(
    sources: list[Path],
    dest_dir: Path,
    on_progress: Optional[ProgressCallback] = None,
    *,
    preserve_metadata: bool = True,
    batch_size: int = 0,
    batch_pause_seconds: float = 0.0,
    progress_every: int = 1,
    should_cancel: Optional[ShouldCancel] = None,
) -> tuple[int, int, int]:
    """
    Copy each source file into ``dest_dir`` using the original file name.

    Args:
        sources: Files to copy.
        dest_dir: Destination directory (created if missing).
        on_progress: Called after file attempts (throttled by ``progress_every``).
        preserve_metadata: Use shutil.copy2 when True.
        batch_size: Files per batch before optional pause; 0 disables batch pauses.
        batch_pause_seconds: Sleep after each full batch when ``batch_size`` > 0.
        progress_every: Emit progress at most every N completed attempts unless forced.
        should_cancel: When it returns True, stop after the current file.

    Returns:
        Tuple of (copied_count, skipped_count, failed_count).
    """
    dest = dest_dir.resolve()
    dest.mkdir(parents=True, exist_ok=True)

    total = len(sources)
    copied = 0
    skipped = 0
    failed = 0
    every = max(1, progress_every)

    _emit(on_progress, total, copied, skipped, failed, "")

    for index, source in enumerate(sources, start=1):
        if should_cancel is not None and should_cancel():
            break

        name = source.name

        if not source.is_file():
            skipped += 1
            _maybe_emit(
                on_progress,
                total,
                copied,
                skipped,
                failed,
                name,
                force=False,
                progress_every=every,
            )
        else:
            target = dest / name
            if target.exists():
                stem = source.stem
                suffix = source.suffix
                n = 1
                while target.exists():
                    target = dest / f"{stem}_{n}{suffix}"
                    n += 1

            try:
                if preserve_metadata:
                    shutil.copy2(source, target)
                else:
                    shutil.copy(source, target)
                copied += 1
            except OSError:
                failed += 1

            _maybe_emit(
                on_progress,
                total,
                copied,
                skipped,
                failed,
                name,
                force=False,
                progress_every=every,
            )

        at_batch_end = batch_size > 0 and index % batch_size == 0 and index < total
        if at_batch_end:
            _emit(on_progress, total, copied, skipped, failed, name)
            if should_cancel is not None and should_cancel():
                break
            if batch_pause_seconds > 0:
                time.sleep(batch_pause_seconds)

    _emit(on_progress, total, copied, skipped, failed, "")
    return copied, skipped, failed
