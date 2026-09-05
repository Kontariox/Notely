import json
from typing import Any, Dict, List, Optional
from app.ai.chunking import format_external_ai_parts


def format_all_data_bundle(
    topic: str,
    subject: str,
    lesson_date: Optional[str],
    notes: Optional[str],
    summary: Optional[str],
    events: Optional[List[Dict[str, Any]]],
    transcription: Optional[str]
) -> str:
    """
    Formats all lesson data into one clean, well-structured document:
    1. Temat
    2. Notatka
    3. Najważniejsze punkty / Streszczenie
    4. Wydarzenia i daty
    5. Zadania
    6. Pełna transkrypcja
    """
    sections = []

    # 1. Header & Topic
    header = f"# MATERIAŁ Z LEKCJI: {topic}\n"
    header += f"Przedmiot: {subject or 'Nieokreślony'} | Data lekcji: {lesson_date or 'Brak daty'}\n"
    sections.append(header)

    # 2. Notes
    if notes:
        sections.append(f"## NOTATKA GŁÓWNA\n{notes}")

    # 3. Summary / Key points
    if summary:
        sections.append(f"## PODSUMOWANIE I NAJWAŻNIEJSZE PUNKTY\n{summary}")

    # 4. Events & Dates
    if events:
        ev_lines = ["## ZAPOWIEDZIANE WYDARZENIA, TERMINY I SPRAWDZIANY\n"]
        for ev in events:
            date_info = ev.get("date") or ev.get("raw_date_expression") or "Brak określonej daty"
            ev_lines.append(
                f"- **{ev.get('title', 'Wydarzenie')}** ({ev.get('type')})\n"
                f"  Termin: {date_info}\n"
                f"  Opis: {ev.get('description', '')}\n"
                f"  Cytat z lekcji: \"{ev.get('source_text', '')}\"\n"
            )
        sections.append("\n".join(ev_lines))

    # 5. Raw Transcription
    if transcription:
        sections.append(f"## PEŁNA ORYGINALNA TRANSKRYPCJA NAGRANIA\n\"\"\"\n{transcription}\n\"\"\"")

    return "\n\n" + ("=" * 60) + "\n\n".join(sections)


def generate_analytical_prompt(
    subject: Optional[str] = None,
    lesson_date: Optional[str] = None,
    topic: Optional[str] = None
) -> str:
    """
    Generates a comprehensive, high-quality analytical prompt for external LLMs
    (ChatGPT, Claude, Gemini) to analyze an attached or pasted lesson transcription.
    """
    subj_str = subject or "Nieokreślony"
    date_str = lesson_date or "Brak daty"
    topic_str = topic or "Lekcja"

    return f"""Jesteś elitarnym asystentem dydaktycznym i ekspertem w tworzeniu wzorcowych materiałów edukacyjnych.
Przeanalizuj załączony plik z transkrypcją nagrania lekcji (lub treść umieszczoną poniżej).

KONTEKST LEKCJI:
- Przedmiot: {subj_str}
- Data lekcji: {date_str}
- Wstępny temat: {topic_str}

TWOJE ZADANIE:
Na podstawie transkrypcji przygotuj kompletną, czytelną i wyczerpującą notatkę edukacyjną w formacie Markdown oraz zestaw powtórzeniowy.

BEZWZGLĘDNE ZASADY ANALIZY:
1. ZAKAZ HALUCYNACJI: Opieraj się WYŁĄCZNIE na faktach padających w nagraniu. Nie dopowiadaj ani nie zmyślaj żadnych definicji, dat ani twierdzeń spoza tekstu.
2. OZNACZANIE NIEPEWNOŚCI: Jeśli fragment wypowiedzi nauczyciela był niewyraźny lub dwuznaczny, oznacz go jako [niepewne / do weryfikacji].
3. SPRAWDZIANY I TERMINY: Wyłap bezwzględnie wszystkie zapowiedziane sprawdziany, kartkówki, zadania domowe i terminy. Przytocz dosłowny cytat z wypowiedzi nauczyciela.
4. DOSTOSOWANIE DO PRZEDMIOTU: Uwzględnij specyfikę przedmiotu (dokładne wzory i twierdzenia dla przedmiotów ścisłych, cytaty i motywy dla języka polskiego, chronologię i postacie dla historii).

WYMAGANA STRUKTURA ODPOWIEDZI:

# Temat lekcji: [Precyzyjny temat wyłoniony z lekcji]
**Przedmiot:** {subj_str} | **Data lekcji:** {date_str}

## 📌 Najważniejsze informacje
- [3 do 6 kluczowych punktów podsumowujących sedno lekcji]

## 📝 Notatka szczegółowa
[Uporządkowany, wyczerpujący i logiczny opis wszystkich omówionych zagadnień z podtytułami ###. Zachowaj merytoryczną treść przekazaną przez nauczyciela.]

## 💡 Kluczowe pojęcia i definicje
- **Pojęcie** — wyjaśnienie
- [Wszystkie definicje formalne podane na lekcji]

## 🔍 Przykłady, zadania i zastosowania
- [Przykłady, zadania lub studia przypadków omówione podczas lekcji]

## ⚠️ Co warto zapamiętać ("Na sprawdzian")
- [Wskazówki nauczyciela, na co zwrócić uwagę, typowe pułapki i błędy]

## 📅 Zapowiedziane sprawdziany, kartkówki i terminy
- [Wszystkie sprawdziany, kartkówki, terminy oddania prac z cytatem wypowiedzi nauczyciela]

## ✍️ Zadania domowe i polecenia
- [Wszystkie zadania zadane do domu lub ćwiczenia do dokończenia]

## 🧠 Fiszki i pytania kontrolne (Sprawdź swoją wiedzę)
- [6-8 pytań kontrolnych sprawdzających zrozumienie lekcji wraz z odpowiedziami]
"""


def format_prompt_with_transcription(
    transcription: str,
    custom_instruction: Optional[str] = None,
    subject: Optional[str] = None,
    lesson_date: Optional[str] = None,
    topic: Optional[str] = None
) -> str:
    """Wraps transcription in a ready-to-use prompt for external LLMs (ChatGPT, Claude, Gemini)."""
    if custom_instruction:
        instruction = custom_instruction
    else:
        instruction = generate_analytical_prompt(subject=subject, lesson_date=lesson_date, topic=topic)

    return (
        f"{instruction}\n\n"
        f"--- POCZĄTEK TRANSKRYPCJI LEKCJI ---\n\n"
        f"{transcription}\n\n"
        f"--- KONIEC TRANSKRYPCJI LEKCJI ---"
    )


def split_transcription_into_downloadable_parts(
    transcription: str,
    base_filename: str = "transkrypcja",
    max_chars: int = 4000
) -> List[Dict[str, str]]:
    """
    Splits long transcription into named parts (e.g. transkrypcja_part_01.md)
    with clear header labels: PART 1/N.
    """
    parts = format_external_ai_parts(transcription, max_chars_per_part=max_chars)
    result = []
    total = len(parts)

    for i, part_text in enumerate(parts, start=1):
        filename = f"{base_filename}_part_{i:02d}_of_{total:02d}.md"
        result.append({
            "filename": filename,
            "part_index": i,
            "total_parts": total,
            "content": part_text
        })

    return result
