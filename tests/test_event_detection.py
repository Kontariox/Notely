import pytest
from app.ai.date_resolver import resolve_relative_date


def test_resolve_explicit_date():
    res = resolve_relative_date("2026-09-15", base_lesson_date="2026-09-03")
    assert res.resolved_date == "2026-09-15"
    assert res.is_calculated is False
    assert res.confidence_penalty == 0.0


def test_resolve_polish_month_date():
    res = resolve_relative_date("15 września 2026", base_lesson_date="2026-09-03")
    assert res.resolved_date == "2026-09-15"
    assert res.is_calculated is False


def test_resolve_jutro():
    res = resolve_relative_date("jutro", base_lesson_date="2026-09-03")
    assert res.resolved_date == "2026-09-04"
    assert res.is_calculated is True


def test_resolve_pojutrze():
    res = resolve_relative_date("pojutrze", base_lesson_date="2026-09-03")
    assert res.resolved_date == "2026-09-05"
    assert res.is_calculated is True


def test_resolve_za_tydzien():
    res = resolve_relative_date("za tydzień", base_lesson_date="2026-09-03")
    assert res.resolved_date == "2026-09-10"
    assert res.is_calculated is True


def test_resolve_za_dwa_tygodnie():
    res = resolve_relative_date("za dwa tygodnie w piątek", base_lesson_date="2026-09-03")
    # Base is 2026-09-03 (Thursday) + 14 days -> 2026-09-17
    assert res.resolved_date == "2026-09-17"
    assert res.is_calculated is True


def test_resolve_za_x_dni():
    res = resolve_relative_date("za 5 dni", base_lesson_date="2026-09-03")
    assert res.resolved_date == "2026-09-08"
    assert res.is_calculated is True


def test_relative_date_without_base_date_preserves_none():
    # Per Requirement 8: If base date is missing, do NOT invent or guess
    res = resolve_relative_date("za dwa tygodnie", base_lesson_date=None)
    assert res.resolved_date is None
    assert res.is_calculated is False
    assert res.confidence_penalty > 0.0
    assert "brak daty lekcji" in res.explanation.lower()
