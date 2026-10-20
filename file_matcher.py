"""Find files under a directory matching glob or regex patterns."""

from __future__ import annotations

import fnmatch
import re
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal, Optional

MatchMode = Literal["glob", "regex"]
ShouldCancel = Callable[[], bool]


@dataclass(frozen=True)
class SearchProgress:
    """Snapshot of search walk progress."""

    scanned: int
    matched: int
    current_dir: str


SearchProgressCallback = Callable[[SearchProgress], None]


def compile_pattern(pattern: str, mode: MatchMode) -> re.Pattern[str] | str:
    """
    Prepare a pattern for matching file names.

    Args:
        pattern: Glob (e.g. ``*.pdf``) or regex string when mode is ``regex``.
        mode: ``glob`` or ``regex``.

    Returns:
        Compiled regex for regex mode, or the glob pattern string for glob mode.
    """
    pattern = pattern.strip()
    if not pattern:
        raise ValueError("Search pattern must not be empty.")
    if mode == "regex":
        return re.compile(pattern)
    return pattern


def file_name_matches(name: str, pattern: re.Pattern[str] | str, mode: MatchMode) -> bool:
    """Return True if ``name`` matches the pattern."""
    if mode == "glob":
        assert isinstance(pattern, str)
        return fnmatch.fnmatch(name, pattern)
    assert isinstance(pattern, re.Pattern)
    return pattern.search(name) is not None


def _narrow_rglob_pattern(pattern: str) -> Optional[str]:
    """
    Return ``*.ext`` for rglob when the glob pattern only differs by a prefix.

    Args:
        pattern: Glob pattern applied to file names.

    Returns:
        Extension glob such as ``*.pdf``, or None when the walk cannot be narrowed.
    """
    if "/" in pattern or "\\" in pattern:
        return None
    match = re.search(r"\*\.([A-Za-z0-9]+)$", pattern)
    if match is None:
        return None
    return f"*.{match.group(1)}"


def _walk_paths(
    root: Path,
    prepared: re.Pattern[str] | str,
    mode: MatchMode,
    *,
    recursive: bool,
) -> Iterator[Path]:
    """Yield candidate file paths using the narrowest practical directory walk."""
    if mode == "glob" and isinstance(prepared, str):
        narrow = _narrow_rglob_pattern(prepared)
        if narrow is not None:
            if recursive:
                yield from root.rglob(narrow)
            else:
                yield from root.glob(narrow)
            return

    if recursive:
        yield from root.rglob("*")
    else:
        yield from root.glob("*")


def _maybe_emit_search(
    callback: Optional[SearchProgressCallback],
    scanned: int,
    matched: int,
    current_dir: str,
    *,
    force: bool,
    progress_every: int,
) -> None:
    if callback is None:
        return
    every = max(1, progress_every)
    if not force and every > 1 and scanned % every != 0:
        return
    callback(SearchProgress(scanned=scanned, matched=matched, current_dir=current_dir))


def iter_matching_files(
    root_dir: Path,
    pattern: str,
    mode: MatchMode = "glob",
    *,
    recursive: bool = True,
    should_cancel: Optional[ShouldCancel] = None,
    on_progress: Optional[SearchProgressCallback] = None,
    batch_size: int = 0,
    batch_pause_seconds: float = 0.0,
    progress_every: int = 1,
) -> Iterator[Path]:
    """
    Yield absolute paths of files whose names match the pattern.

    Args:
        root_dir: Directory to search.
        pattern: Glob or regex pattern applied to each file name.
        mode: ``glob`` or ``regex``.
        recursive: If True, walk subdirectories.
        should_cancel: When it returns True, stop the walk.
        on_progress: Called during the walk (throttled by ``progress_every``).
        batch_size: Pause after this many matches when > 0.
        batch_pause_seconds: Sleep after each search batch when ``batch_size`` > 0.
        progress_every: Emit search progress every N scanned entries unless forced.

    Yields:
        Absolute paths of matching files.
    """
    root = root_dir.resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {root}")

    prepared = compile_pattern(pattern, mode)
    scanned = 0
    matched = 0
    every = max(1, progress_every)

    _maybe_emit_search(on_progress, 0, 0, str(root), force=True, progress_every=every)

    for path in _walk_paths(root, prepared, mode, recursive=recursive):
        if should_cancel is not None and should_cancel():
            break

        scanned += 1
        current_dir = str(path.parent)

        if not path.is_file():
            _maybe_emit_search(
                on_progress,
                scanned,
                matched,
                current_dir,
                force=False,
                progress_every=every,
            )
            continue

        if not file_name_matches(path.name, prepared, mode):
            _maybe_emit_search(
                on_progress,
                scanned,
                matched,
                current_dir,
                force=False,
                progress_every=every,
            )
            continue

        matched += 1
        _maybe_emit_search(
            on_progress,
            scanned,
            matched,
            current_dir,
            force=True,
            progress_every=every,
        )
        yield path.resolve()

        at_batch_end = batch_size > 0 and matched % batch_size == 0
        if at_batch_end and batch_pause_seconds > 0:
            if should_cancel is not None and should_cancel():
                break
            time.sleep(batch_pause_seconds)

    _maybe_emit_search(on_progress, scanned, matched, str(root), force=True, progress_every=every)


def find_matching_files(
    root_dir: Path,
    pattern: str,
    mode: MatchMode = "glob",
    *,
    recursive: bool = True,
    should_cancel: Optional[ShouldCancel] = None,
    on_progress: Optional[SearchProgressCallback] = None,
    batch_size: int = 0,
    batch_pause_seconds: float = 0.0,
    progress_every: int = 1,
) -> list[Path]:
    """
    Collect absolute paths of files whose names match the pattern.

    Args:
        root_dir: Directory to search.
        pattern: Glob or regex pattern applied to each file name.
        mode: ``glob`` or ``regex``.
        recursive: If True, walk subdirectories.
        should_cancel: When it returns True, stop the walk.
        on_progress: Called during the walk (throttled by ``progress_every``).
        batch_size: Pause after this many matches when > 0.
        batch_pause_seconds: Sleep after each search batch when ``batch_size`` > 0.
        progress_every: Emit search progress every N scanned entries unless forced.

    Returns:
        Sorted list of absolute file paths.
    """
    results = list(
        iter_matching_files(
            root_dir,
            pattern,
            mode,
            recursive=recursive,
            should_cancel=should_cancel,
            on_progress=on_progress,
            batch_size=batch_size,
            batch_pause_seconds=batch_pause_seconds,
            progress_every=progress_every,
        )
    )
    results.sort(key=lambda p: str(p).lower())
    return results
