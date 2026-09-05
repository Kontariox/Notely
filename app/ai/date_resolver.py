import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional, Tuple


@dataclass
class DateResolutionResult:
    resolved_date: Optional[str]  # YYYY-MM-DD or None
    is_calculated: bool
    confidence_penalty: float
    explanation: str


POLISH_MONTHS = {
    "stycznia": 1, "styczeń": 1,
    "lutego": 2, "luty": 2,
    "marca": 3, "marzec": 3,
    "kwietnia": 4, "kwiecień": 4,
    "maja": 5, "maj": 5,
    "czerwca": 6, "czerwiec": 6,
    "lipca": 7, "lipiec": 7,
    "sierpnia": 8, "sierpień": 8,
    "września": 9, "wrzesień": 9,
    "października": 10, "październik": 10,
    "listopada": 11, "listopad": 11,
    "grudnia": 12, "grudzień": 12
}

POLISH_WEEKDAYS = {
    "poniedziałek": 0, "poniedziałku": 0,
    "wtorek": 1, "wtorku": 1,
    "środę": 2, "środa": 2, "środy": 2,
    "czwartek": 3, "czwartku": 3,
    "piątek": 4, "piątku": 4,
    "sobotę": 5, "sobota": 5, "soboty": 5,
    "niedzielę": 6, "niedziela": 6, "niedzieli": 6
}

WORD_NUMBERS = {
    "jeden": 1, "jedenastu": 11,
    "dwa": 2, "dwóch": 2, "dwie": 2,
    "trzy": 3, "trzech": 3,
    "cztery": 4, "czterech": 4,
    "pięć": 5, "pięciu": 5,
    "sześć": 6, "sześciu": 6,
    "siedem": 7, "siedmiu": 7
}


def parse_iso_date(date_str: str) -> Optional[date]:
    """Attempts to parse YYYY-MM-DD or YYYY.MM.DD."""
    for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%d.%m.%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            pass
    return None


def resolve_relative_date(
    raw_expression: Optional[str],
    base_lesson_date: Optional[str] = None
) -> DateResolutionResult:
    """
    Safely resolves relative and absolute Polish date expressions.
    If base_lesson_date is missing or ambiguous, does NOT invent or guess dates.
    """
    if not raw_expression or not raw_expression.strip():
        return DateResolutionResult(
            resolved_date=None,
            is_calculated=False,
            confidence_penalty=0.0,
            explanation="Brak określonej daty w wypowiedzi"
        )

    expr = raw_expression.strip().lower()

    # 1. Check if raw expression is already an explicit ISO or dot-separated date
    iso_match = re.search(r'\b(20\d\d[-/.][01]?\d[-/.][0-3]?\d)\b', expr)
    if iso_match:
        parsed = parse_iso_date(iso_match.group(1))
        if parsed:
            return DateResolutionResult(
                resolved_date=parsed.isoformat(),
                is_calculated=False,
                confidence_penalty=0.0,
                explanation=f"Wyraźna data w tekście: {parsed.isoformat()}"
            )

    # 2. Check for "DD [miesiąc] (YYYY)" pattern (e.g. "15 września", "3 maja 2026")
    month_regex = r'\b(\d{1,2})\s+(' + '|'.join(POLISH_MONTHS.keys()) + r')(?:\s+(20\d\d))?\b'
    m_match = re.search(month_regex, expr)
    if m_match:
        day = int(m_match.group(1))
        month = POLISH_MONTHS[m_match.group(2)]
        year = int(m_match.group(3)) if m_match.group(3) else None

        if not year:
            if base_lesson_date:
                base_dt = parse_iso_date(base_lesson_date)
                year = base_dt.year if base_dt else datetime.now().year
            else:
                year = datetime.now().year

        try:
            resolved = date(year, month, day)
            return DateResolutionResult(
                resolved_date=resolved.isoformat(),
                is_calculated=False,
                confidence_penalty=0.0,
                explanation=f"Wyraźna data z nazwą miesiąca: {day} {m_match.group(2)} {year}"
            )
        except ValueError:
            pass

    # 3. If there is no base date, we CANNOT resolve relative terms honestly
    if not base_lesson_date:
        return DateResolutionResult(
            resolved_date=None,
            is_calculated=False,
            confidence_penalty=0.15,
            explanation=f"Wyrażenie względne '{raw_expression}' - brak daty lekcji do wyliczenia konkretnego dnia."
        )

    base_dt = parse_iso_date(base_lesson_date)
    if not base_dt:
        return DateResolutionResult(
            resolved_date=None,
            is_calculated=False,
            confidence_penalty=0.15,
            explanation=f"Nieprawidłowa data bazowa: {base_lesson_date}"
        )

    # 4. Resolve relative expressions against base_dt

    # "jutro"
    if "jutro" in expr and "pojutrze" not in expr:
        target = base_dt + timedelta(days=1)
        return DateResolutionResult(
            resolved_date=target.isoformat(),
            is_calculated=True,
            confidence_penalty=0.05,
            explanation=f"Wyliczono 'jutro' na podstawie daty lekcji {base_dt} -> {target.isoformat()}"
        )

    # "pojutrze"
    if "pojutrze" in expr:
        target = base_dt + timedelta(days=2)
        return DateResolutionResult(
            resolved_date=target.isoformat(),
            is_calculated=True,
            confidence_penalty=0.05,
            explanation=f"Wyliczono 'pojutrze' na podstawie daty lekcji {base_dt} -> {target.isoformat()}"
        )

    # "za tydzień" / "za 1 tydzień"
    if re.search(r'\bza\s+(?:jeden\s+)?tydzień\b', expr):
        target = base_dt + timedelta(days=7)
        return DateResolutionResult(
            resolved_date=target.isoformat(),
            is_calculated=True,
            confidence_penalty=0.05,
            explanation=f"Wyliczono 'za tydzień' (+7 dni) od daty lekcji {base_dt} -> {target.isoformat()}"
        )

    # "za dwa tygodnie" / "za 2 tygodnie"
    weeks_match = re.search(r'\bza\s+(\d+|dwa|dwie|trzy|cztery)\s+tygodn', expr)
    if weeks_match:
        w_raw = weeks_match.group(1)
        num_weeks = int(w_raw) if w_raw.isdigit() else WORD_NUMBERS.get(w_raw, 2)
        target = base_dt + timedelta(days=7 * num_weeks)
        return DateResolutionResult(
            resolved_date=target.isoformat(),
            is_calculated=True,
            confidence_penalty=0.05,
            explanation=f"Wyliczono 'za {num_weeks} tyg.' (+{7*num_weeks} dni) od daty lekcji {base_dt} -> {target.isoformat()}"
        )

    # "za X dni"
    days_match = re.search(r'\bza\s+(\d+|dwa|trzy|cztery|pięć|sześć|siedem)\s+dn', expr)
    if days_match:
        d_raw = days_match.group(1)
        num_days = int(d_raw) if d_raw.isdigit() else WORD_NUMBERS.get(d_raw, 3)
        target = base_dt + timedelta(days=num_days)
        return DateResolutionResult(
            resolved_date=target.isoformat(),
            is_calculated=True,
            confidence_penalty=0.05,
            explanation=f"Wyliczono 'za {num_days} dni' (+{num_days} dni) od daty lekcji {base_dt} -> {target.isoformat()}"
        )

    # Days of week (e.g. "w piątek", "w następny piątek", "w przyszły wtorek")
    weekday_match = re.search(r'\b(przyszł[yąe]|następn[yąe]|najbliższ[yąe])?\s*(?:w|we)?\s*(' + '|'.join(POLISH_WEEKDAYS.keys()) + r')\b', expr)
    if weekday_match:
        modifier = weekday_match.group(1) or ""
        day_name = weekday_match.group(2)
        target_weekday = POLISH_WEEKDAYS[day_name]
        current_weekday = base_dt.weekday()

        days_ahead = (target_weekday - current_weekday) % 7
        if days_ahead == 0:
            days_ahead = 7  # Next week if same day

        if "następn" in modifier or "przyszł" in modifier:
            if days_ahead < 4:
                days_ahead += 7

        target = base_dt + timedelta(days=days_ahead)
        return DateResolutionResult(
            resolved_date=target.isoformat(),
            is_calculated=True,
            confidence_penalty=0.1,
            explanation=f"Wyliczono dzień tygodnia '{day_name}' ({modifier}) z daty lekcji {base_dt} -> {target.isoformat()}"
        )

    # Unresolvable relative date
    return DateResolutionResult(
        resolved_date=None,
        is_calculated=False,
        confidence_penalty=0.1,
        explanation=f"Zachowano oryginalne sformułowanie: '{raw_expression}'"
    )
