"""Conservative answer extraction for the numeric pilot benchmark."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
FINAL_ANSWER = re.compile(r"FINAL_ANSWER\s*:\s*([^\n]+)", re.IGNORECASE)
NUMBER = re.compile(r"[-+]?\d+(?:\.\d+)?")


def canonicalize_numeric_answer(text: str) -> str | None:
    """Extract an explicitly marked numeric final answer without guessing from a trace."""
    match = FINAL_ANSWER.search(text.translate(DEVANAGARI_DIGITS))
    if not match:
        return None
    numbers = NUMBER.findall(match.group(1).replace(",", ""))
    if len(numbers) != 1:
        return None
    try:
        value = Decimal(numbers[0])
    except InvalidOperation:
        return None
    if value == value.to_integral_value():
        return str(value.to_integral_value())
    return format(value.normalize(), "f").rstrip("0").rstrip(".")


def numeric_answers_match(predicted: str | None, expected: str) -> bool:
    if predicted is None:
        return False
    try:
        return Decimal(predicted) == Decimal(expected.translate(DEVANAGARI_DIGITS).replace(",", ""))
    except InvalidOperation:
        return False


LETTERS = [chr(ord("A") + i) for i in range(26)]


def canonicalize_choice_answer(text: str, choices: list[str] | None = None) -> str | None:
    """Extract an explicitly marked multiple-choice final answer.

    Accepts either the option letter (A, B, C, ...) or the choice text itself (with or
    without the letter prefix, markdown emphasis, and trailing punctuation) when the
    choices are supplied. Matching is position-based and case/period-insensitive, so a
    translated choice (Hindi) may be matched against the original (English) choice list
    via the caller supplying both. Returns the normalized letter, or None when no
    unambiguous match is found.
    """
    import re as _re

    match = FINAL_ANSWER.search(text.translate(DEVANAGARI_DIGITS))
    if not match:
        return None
    raw = match.group(1).strip()
    if not raw:
        return None

    def _normalize(value: str) -> str:
        value = _re.sub(r"[*_`\"]", "", value)
        value = _re.sub(r"[)>\]]$", "", value.strip())
        value = value.replace(".", "").replace(",", "")
        return value.strip().rstrip(".,;:।)").strip().lower()

    stripped = _normalize(raw)
    letter = _re.fullmatch(r"[A-Za-z]", stripped)
    if letter:
        return letter.group(0).upper()
    if choices:
        prefixless = None
        prefix = _re.match(r"^[A-Za-z]\s*[).:\-*]\s*", raw)
        if prefix:
            prefixless = _normalize(raw[prefix.end():])
        candidates = set()
        for position, choice in enumerate(choices):
            normalized_choice = _normalize(choice)
            if stripped == normalized_choice or (prefixless and prefixless == normalized_choice):
                candidates.add(position)
        if len(candidates) == 1:
            return LETTERS[candidates.pop()]
    return None


def choice_answers_match(predicted: str | None, expected: str) -> bool:
    if predicted is None:
        return False
    return predicted.upper() == expected.translate(DEVANAGARI_DIGITS).strip().upper()
