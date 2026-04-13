"""Tests for citation / quote / code / LaTeX preservation."""
from __future__ import annotations

from app.humanizer import preserve


def _kinds(spans):
    return sorted(s.kind for s in spans)


def test_finds_author_year_brackets():
    spans = preserve.find_spans("As shown in [Smith 2024], the results confirm.")
    assert len(spans) == 1
    assert spans[0].kind == "citation"
    assert spans[0].text == "[Smith 2024]"


def test_finds_author_year_parens_with_comma():
    spans = preserve.find_spans("Recent work (Smith, 2024) highlights this.")
    assert len(spans) == 1
    assert spans[0].kind == "citation"


def test_finds_et_al():
    spans = preserve.find_spans("As (Smith et al., 2024) demonstrated.")
    assert len(spans) == 1
    assert "et al" in spans[0].text


def test_finds_numeric_citations():
    spans = preserve.find_spans("The model [1] beats [2, 3] and [4-6].")
    kinds = _kinds(spans)
    assert kinds == ["citation", "citation", "citation"]
    assert any(s.text == "[1]" for s in spans)
    assert any(s.text == "[4-6]" for s in spans)


def test_finds_quotes():
    spans = preserve.find_spans('He said "this is important" to the class.')
    assert len(spans) == 1
    assert spans[0].kind == "quote"


def test_finds_code_fence():
    src = "Run `git status` or\n\n```python\nprint('hi')\n```\n\nthen commit."
    spans = preserve.find_spans(src)
    kinds = _kinds(spans)
    assert kinds == ["code", "code"]


def test_inline_code_inside_fence_not_double_matched():
    src = "```\na `nested` b\n```"
    spans = preserve.find_spans(src)
    # One span, not two — the block fence wins
    assert len(spans) == 1
    assert spans[0].kind == "code"


def test_finds_latex():
    spans = preserve.find_spans("Given $E = mc^2$ and $$\\sum x_i$$ we see.")
    kinds = _kinds(spans)
    assert kinds == ["latex", "latex"]


def test_protect_restore_roundtrip():
    original = (
        'Per [Smith 2024], the formula $E=mc^2$ applies. '
        'He wrote "hello" in the margin.'
    )
    protected, spans = preserve.protect(original)

    assert len(spans) == 3
    assert "[Smith 2024]" not in protected
    assert "$E=mc^2$" not in protected
    assert '"hello"' not in protected
    assert "\u27e8\u27e8" in protected  # placeholders present

    restored = preserve.restore(protected, spans)
    assert restored == original


def test_restore_tolerates_missing_placeholder():
    original = "Per [Smith 2024], the formula applies."
    protected, spans = preserve.protect(original)
    # Simulate LLM dropping one placeholder
    damaged = protected.replace("\u27e8\u27e8", "removed\u27e8\u27e8")
    restored = preserve.restore(damaged, spans)
    # Should still include the citation (placeholder intact) and our junk
    assert "[Smith 2024]" in restored


def test_has_placeholders_detects_them():
    protected, _ = preserve.protect("Per [Smith 2024] it works.")
    assert preserve.has_placeholders(protected)
    assert not preserve.has_placeholders("plain text")


def test_non_overlapping_spans():
    """A code fence containing pseudo-citations should not re-match them."""
    src = "Normal text [Smith 2024]. Code:\n```\nrefs like [Jones 2023]\n```"
    spans = preserve.find_spans(src)
    kinds = _kinds(spans)
    # One citation, one code block — the citation inside the fence is not re-detected
    assert kinds == ["citation", "code"]


def test_empty_text():
    assert preserve.find_spans("") == []
    protected, spans = preserve.protect("")
    assert protected == ""
    assert spans == []


def test_text_with_no_spans():
    text = "Just plain text with nothing special."
    protected, spans = preserve.protect(text)
    assert protected == text
    assert spans == []
