"""Citation-aware rewriting: detect spans that must not be mangled by the LLM.

Academic writers' #1 complaint with humanizers is citations getting
paraphrased into garbage.  This module finds such spans — inline citations,
quotations, code, LaTeX math — replaces them with unique placeholder tokens
before rewriting, and restores them verbatim afterwards.

Design:
  - Use unicode angle-bracket placeholders (⟨⟨N⟩⟩) that virtually never
    appear in English prose and signal "leave alone" to the LLM.
  - The rewriter prompt (rewriter.py) explicitly instructs preservation.
  - Overlapping spans are resolved in favour of the outermost / first match,
    so `[code]` inside a "quote" is kept as-is once.

Trade-off vs spaCy NER: regex covers ~95% of academic citation patterns
(`[Smith 2024]`, `(Author, 2024)`, `[1]`, `[1-5]`) at zero cost.  spaCy
gains maybe 5% precision at 500 MB of model weight — deferred.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

SpanKind = Literal["citation", "quote", "code", "latex"]

# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------
# Author-year styles: [Smith 2024], [Smith, 2024], [Smith and Jones 2024],
# [Smith et al. 2024], [Smith et al., 2024], with optional suffix "2024a".
_AUTHOR_YEAR_BRACKET = re.compile(
    r"\[[A-Z][A-Za-z'\-]+"
    r"(?:\s+(?:and|&)\s+[A-Z][A-Za-z'\-]+)?"
    r"(?:\s+et\s+al\.?)?"
    r",?\s+\d{4}[a-z]?\]",
)
_AUTHOR_YEAR_PAREN = re.compile(
    r"\([A-Z][A-Za-z'\-]+"
    r"(?:\s+(?:and|&)\s+[A-Z][A-Za-z'\-]+)?"
    r"(?:\s+et\s+al\.?)?"
    r",\s*\d{4}[a-z]?\)",
)
# Numeric styles: [1], [1,2,3], [1-5], [1–5]
_NUMERIC_BRACKET = re.compile(r"\[\d+(?:[\s,]+\d+)*\]|\[\d+\s*[-–]\s*\d+\]")

# Block code fences before inline backticks so the inline regex doesn't eat
# their contents.
_CODE_FENCE = re.compile(r"```[\s\S]*?```")
_INLINE_CODE = re.compile(r"`[^`\n]+?`")

# LaTeX: $$...$$ before $...$ for the same reason.
_LATEX_BLOCK = re.compile(r"\$\$[\s\S]*?\$\$")
_LATEX_INLINE = re.compile(r"\$[^$\n]+?\$")

# Quotations — only straight + curly double quotes.  Single quotes are too
# noisy (contractions, possessives) to safely preserve by default.
_DOUBLE_QUOTE = re.compile(r"\"[^\"\n]+?\"|\u201c[^\u201d\n]+?\u201d")


PATTERNS: list[tuple[re.Pattern, SpanKind]] = [
    # Order matters — block-scoped things first so they don't get shadowed.
    (_CODE_FENCE, "code"),
    (_LATEX_BLOCK, "latex"),
    (_INLINE_CODE, "code"),
    (_LATEX_INLINE, "latex"),
    (_AUTHOR_YEAR_BRACKET, "citation"),
    (_AUTHOR_YEAR_PAREN, "citation"),
    (_NUMERIC_BRACKET, "citation"),
    (_DOUBLE_QUOTE, "quote"),
]


@dataclass(frozen=True)
class PreservedSpan:
    start: int
    end: int
    text: str
    kind: SpanKind


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------
def find_spans(text: str) -> list[PreservedSpan]:
    """Find all preserve-worthy spans, non-overlapping, sorted by position.

    If two patterns match overlapping regions, earlier-listed patterns win
    (block code/latex beats inline quotes, etc.).
    """
    spans: list[PreservedSpan] = []
    taken: list[tuple[int, int]] = []  # ranges already claimed

    for pattern, kind in PATTERNS:
        for m in pattern.finditer(text):
            s, e = m.start(), m.end()
            if _overlaps_any(s, e, taken):
                continue
            spans.append(PreservedSpan(start=s, end=e, text=m.group(), kind=kind))
            taken.append((s, e))

    spans.sort(key=lambda sp: sp.start)
    return spans


def _overlaps_any(start: int, end: int, ranges: list[tuple[int, int]]) -> bool:
    return any(not (end <= rs or start >= re_) for rs, re_ in ranges)


# ---------------------------------------------------------------------------
# Protect / restore
# ---------------------------------------------------------------------------
def _placeholder(index: int) -> str:
    # Unicode angle brackets — extraordinarily rare in normal prose.
    return f"\u27e8\u27e8{index}\u27e9\u27e9"


PLACEHOLDER_RE = re.compile(r"\u27e8\u27e8(\d+)\u27e9\u27e9")


def protect(text: str) -> tuple[str, list[PreservedSpan]]:
    """Replace each detected span with a placeholder token.

    Returns (protected_text, originals).  `originals[i]` is the span that
    maps to placeholder index `i`.
    """
    spans = find_spans(text)
    if not spans:
        return text, []

    out_parts: list[str] = []
    cursor = 0
    for i, span in enumerate(spans):
        out_parts.append(text[cursor : span.start])
        out_parts.append(_placeholder(i))
        cursor = span.end
    out_parts.append(text[cursor:])
    return "".join(out_parts), spans


def restore(text: str, originals: list[PreservedSpan]) -> str:
    """Replace placeholders with the original span text.

    Missing placeholders are silently dropped — if the LLM ate one, the user
    gets a slightly-shorter result rather than a broken placeholder string.
    """
    if not originals:
        return text

    def sub(match: re.Match) -> str:
        idx = int(match.group(1))
        if 0 <= idx < len(originals):
            return originals[idx].text
        return ""  # unknown placeholder — drop it

    return PLACEHOLDER_RE.sub(sub, text)


def has_placeholders(text: str) -> bool:
    return bool(PLACEHOLDER_RE.search(text))


def placeholder_prompt_note() -> str:
    """Sentence to append to the LLM system prompt so it respects markers."""
    return (
        "The text may contain placeholder tokens in the form \u27e8\u27e8N\u27e9\u27e9 "
        "(angle brackets around a number). These are sacred — keep them "
        "EXACTLY as-is, in the same positions. Do not translate, paraphrase, "
        "delete, or add them."
    )
