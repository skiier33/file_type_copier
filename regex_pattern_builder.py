"""Build filename regex patterns from keywords with AND/OR between terms."""

from __future__ import annotations

import re
from typing import Literal, Sequence

CombineOp = Literal["AND", "OR"]


def _term_pattern(keyword: str) -> str:
    """Return a lookahead subpattern requiring ``keyword`` in the name."""
    return f"(?=.*{re.escape(keyword.strip())})"


def build_filename_regex(
    keywords: Sequence[str],
    operators: Sequence[CombineOp],
    *,
    extension: str = "pdf",
    case_insensitive: bool = True,
) -> str:
    """
    Build a regex matched against file names (``re.search``).

    Keywords are combined left-to-right using ``operators[i]`` between
    ``keywords[i]`` and ``keywords[i + 1]``.

    Args:
        keywords: Non-empty terms to find in the file name.
        operators: Length must be ``len(keywords) - 1``; each value is ``AND`` or ``OR``.
        extension: Required file extension without a leading dot.
        case_insensitive: When True, prefix the pattern with ``(?i)``.

    Returns:
        Regex string requiring the extension and keyword expression.

    Raises:
        ValueError: When inputs are empty or lengths disagree.
    """
    terms = [k.strip() for k in keywords if k.strip()]
    if not terms:
        raise ValueError("Enter at least one keyword.")

    if len(terms) == 1 and operators:
        raise ValueError("Too many operators for a single keyword.")
    if len(terms) > 1 and len(operators) != len(terms) - 1:
        raise ValueError("Each keyword after the first needs AND or OR.")

    expr = _term_pattern(terms[0])
    for op, keyword in zip(operators, terms[1:], strict=True):
        next_part = _term_pattern(keyword)
        if op == "AND":
            expr = f"{expr}{next_part}"
        else:
            expr = f"(?:{expr}|{next_part})"

    ext = extension.strip().lstrip(".")
    if not ext:
        raise ValueError("Enter a file extension (for example pdf).")

    ext_part = f"(?=.*\\.{re.escape(ext)}$)"
    prefix = "(?i)" if case_insensitive else ""
    return f"{prefix}{expr}{ext_part}"


def preview_filename_regex(
    keywords: Sequence[str],
    operators: Sequence[CombineOp],
    *,
    extension: str = "pdf",
    case_insensitive: bool = True,
) -> str:
    """
    Like ``build_filename_regex`` but returns an empty string when inputs are incomplete.

    Args:
        keywords: Keyword fields from the UI (every slot must be non-empty).
        operators: AND/OR choices between consecutive keywords.
        extension: Required extension without a leading dot.
        case_insensitive: When True, use case-insensitive matching.

    Returns:
        Regex string, or ``""`` when the form is not ready.
    """
    terms = [k.strip() for k in keywords]
    if not terms or any(not k for k in terms):
        return ""
    if len(terms) > 1 and len(operators) != len(terms) - 1:
        return ""
    try:
        return build_filename_regex(
            terms,
            list(operators),
            extension=extension,
            case_insensitive=case_insensitive,
        )
    except ValueError:
        return ""
