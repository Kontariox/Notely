import pytest
from app.ai.nvidia_nim import NvidiaNimProvider


def test_extract_json_markdown_block():
    provider = NvidiaNimProvider(api_key="test-key")
    raw_response = """Oto wyodrębnione wydarzenia z lekcji:
```json
{
  "events": [
    {
      "type": "test",
      "title": "Sprawdzian z historii",
      "raw_date_expression": "za dwa tygodnie w piątek",
      "date": null,
      "time": null,
      "description": "I wojna światowa",
      "confidence": 0.95,
      "source_text": "Sprawdzian za dwa tygodnie w piątek."
    }
  ]
}
```
Mam nadzieję, że to pomoże!"""

    result = provider._extract_json_from_response(raw_response)
    assert "events" in result
    assert len(result["events"]) == 1
    assert result["events"][0]["title"] == "Sprawdzian z historii"
    assert result["events"][0]["type"] == "test"


def test_extract_json_plain_object():
    provider = NvidiaNimProvider(api_key="test-key")
    raw_response = '{"events": [{"type": "quiz", "title": "Kartkówka", "confidence": 0.88}]}'
    result = provider._extract_json_from_response(raw_response)
    assert len(result.get("events", [])) == 1
    assert result["events"][0]["type"] == "quiz"


def test_extract_json_embedded():
    provider = NvidiaNimProvider(api_key="test-key")
    raw_response = 'Przeanalizowałem tekst i znalazłem: {"events": [{"type": "homework", "title": "Zadanie 4"}]} Koniec analizy.'
    result = provider._extract_json_from_response(raw_response)
    assert len(result.get("events", [])) == 1
    assert result["events"][0]["title"] == "Zadanie 4"


def test_extract_json_corrupted_fallback():
    provider = NvidiaNimProvider(api_key="test-key")
    raw_response = "Niestety nie byłem w stanie wygenerować JSON: { niesparowane nawiasy"
    result = provider._extract_json_from_response(raw_response)
    assert isinstance(result, dict)
    assert "events" in result
    assert result["events"] == []
