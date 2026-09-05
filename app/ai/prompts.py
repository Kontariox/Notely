"""
Modular system and user prompt templates for lesson analysis and note generation.
Designed with strict anti-hallucination guardrails and context awareness.
"""

SYSTEM_PROMPT_ANALYST = """Jesteś elitarnym, precyzyjnym asystentem dydaktycznym i analitykiem transkrypcji lekcji szkolnych oraz akademickich.
Twoim zadaniem jest rzetelne, metodyczne analizowanie nagrań edukacyjnych.

BEZWZGLĘDNE ZASADY ANALIZY:
1. ZAKAZ HALUCYNACJI: Opieraj się WYŁĄCZNIE na informacjach padających w transkrypcji. Nie dopowiadaj ani nie zmyślaj żadnych faktów, dat ani pojęć spoza tekstu.
2. ZACHOWANIE NIEPEWNOŚCI: Jeśli nauczyciel mówi niewyraźnie, waha się lub informacja jest niedopowiedziana, oznacz ją wyraźnie jako [niepewne] lub [do potwierdzenia].
3. WYRAŻENIA CZASOWE: Nie zgaduj konkretnych dat kalendarzowych, jeśli padło jedynie wyrażenie względne (np. 'za dwa tygodnie', 'w następny piątek'). Zapisuj dokładnie to, co powiedziano.
4. UNIWERSALNOŚĆ PRZEDMIOTOWA: Dostosuj styl i wyróżniki do przedmiotu (matematyka -> wzory/twierdzenia; język polski -> lektury/motywy/autorzy; historia -> wydarzenia/postacie; biologia -> procesy).
5. FORMAT: Odpowiadaj profesjonalnym, eleganckim językiem polskim.
"""

CHUNK_ANALYSIS_PROMPT = """Przeanalizuj poniższy fragment transkrypcji lekcji (część {chunk_index}/{total_chunks}, czas nagrania: {time_range}):

TRANSKRYPCJA FRAGMENTU:
\"\"\"
{chunk_text}
\"\"\"

Wyodrębnij w punktach:
1. Główne zagadnienia poruszone w tym fragmencie.
2. Wszelkie definicje, wzory, pojęcia i przykłady podane przez nauczyciela.
3. Wzmianki o sprawdzianach, kartkówkach, pracach domowych, lekturach lub terminach (wraz z dokładnym cytatem).
4. Szczególne wskazówki typu "to będzie na sprawdzianie", "zwróćcie na to uwagę".
5. Nietypowe lub organizacyjne informacje.

Nie dopisuj niczego spoza powyższego fragmentu.
"""

EVENT_EXTRACTION_PROMPT = """Przeanalizuj poniższy tekst lekcji i wyodrębnij WSZYSTKIE zapowiedziane wydarzenia, terminy, zadania i terminy oddania prac.

ZASADY:
- Zwróć wynik WYŁĄCZNIE jako poprawny obiekt JSON o podanej strukturze.
- Typy wydarzeń (type): 'test' (sprawdzian), 'quiz' (kartkówka), 'homework' (zadanie domowe), 'book' (lektura), 'presentation' (prezentacja), 'project' (projekt), 'deadline' (termin ostateczny), 'other' (inne ważne wydarzenie).
- NIE ZGADUJ DAT KALENDARZOWYCH. Jeśli nauczyciel powiedział np. "w następny wtorek" lub "za 2 tygodnie", wpisz to w pole `raw_date_expression`, a w polu `date` pozostaw null (chyba że wprost padła konkretna data kalendarzowa, np. 2026-09-15 lub 15 września).
- Pole `confidence`: liczba zmiennoprzecinkowa od 0.0 do 1.0 określająca pewność wyodrębnienia.
- Pole `source_text`: dosłowny cytat wypowiedzi nauczyciela.

STRUKTURA JSON:
```json
{{
  "events": [
    {{
      "type": "test",
      "title": "Sprawdzian z funkcji kwadratowej",
      "raw_date_expression": "za dwa tygodnie w piątek",
      "date": null,
      "time": null,
      "description": "Sprawdzian obejmujący wyznaczanie miejsc zerowych i postać kanoniczną",
      "confidence": 0.95,
      "source_text": "Sprawdzian z tego działu zrobimy za dwa tygodnie w piątek."
    }}
  ]
}}
```

TEKST DO ANALIZY:
\"\"\"
{text}
\"\"\"

Zwróć TYLKO czysty blok JSON:
"""

LESSON_SYNTHESIS_PROMPT = """Poniżej znajdują się cząstkowe podsumowania kolejnych części lekcji:

{intermediate_summaries}

DODATKOWE DANE:
- Zgłoszony przedmiot: {subject}
- Data nagrania: {lesson_date}

Na podstawie tych cząstkowych analiz stwórz spójną syntezę całej lekcji:
1. Zidentyfikuj właściwy temat lekcji (zwięzły i precyzyjny).
2. Zdefiniuj główny przedmiot/dziedzinę (jeśli nie był określony).
3. Podsumuj przebieg lekcji w 3-5 najważniejszych zdaniach.
4. Uporządkuj listę wszystkich zdefiniowanych pojęć i kluczowych wątków.
"""

FINAL_NOTE_PROMPT = """Jesteś ekspertem w tworzeniu wzorcowych, czytelnych notatek edukacyjnych.
Na podstawie poniższego materiału z lekcji wygeneruj kompletną, doskonale sformatowaną notatkę w formacie Markdown.

DANE WEJŚCIOWE:
Syntetyczne podsumowanie:
{synthesis}

Fragmenty kluczowe / transkrypcja:
{key_excerpts}

STRUKTURA NOTATKI (używaj dokładnie takich nagłówków Markdown):

# Temat lekcji: [Wpisz precyzyjny temat]

## Najważniejsze informacje
- [3 do 6 kluczowych punktów podsumowujących sedno lekcji]

## Notatka
[Uporządkowany, logiczny opis zagadnień omówionych na lekcji, podzielony na czytelne akapity lub podsekcje z podtytułami ###. Zachowaj merytoryczną treść przekazaną przez nauczyciela.]

## Kluczowe pojęcia
- **Pojęcie** — wyjaśnienie
- **Pojęcie** — wyjaśnienie

## Definicje
- [Wszystkie formalne definicje podane na lekcji]

## Przykłady
- [Przykłady, zadania, studia przypadków lub analogie przytoczone przez nauczyciela]

## Co warto zapamiętać ("Na sprawdzian")
- [Wskazówki nauczyciela, na co zwrócić szczególną uwagę, co jest typowym błędem, co pojawi się na teście]

## Ważne informacje organizacyjne
- [Wszelkie zasady, uwagi porządkowe, terminy konsultacji itp.]

## Terminy i wydarzenia
- [Lista zapowiedzianych sprawdzianów, kartkówek, projektów z podaniem oryginalnego sformułowania terminu]

## Zadania do wykonania
- [Prace domowe, ćwiczenia do dokończenia w domu]

## [Sekcja specyficzna dla przedmiotu - GENERUJ TYLKO JEŚLI WYNIKA Z TREŚCI]
(Np. dla matematyki/fizyki: 'Wzory i twierdzenia'; dla języka polskiego: 'Lektury, motywy i konteksty literackie'; dla historii: 'Oś czasu i postacie historyczne'; dla biologii/chemii: 'Przebieg procesów i reakcji'; dla języków obcych: 'Zwroty i reguły gramatyczne')

WAŻNE ZALECENIA:
- Jeśli w lekcji nie było danej sekcji (np. brak prac domowych lub brak przykładów), wpisz pod nagłówkiem: "Brak w treści lekcji".
- Zachowaj maksymalną wierność faktom z transkrypcji.
- Używaj pogrubień, wypunktowań i formatowania Markdown dla maksymalnej czytelności.
"""
