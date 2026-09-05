import io
import pytest
from app.exports.srt_exporter import export_to_srt, export_to_vtt, format_timestamp_srt, format_timestamp_vtt
from app.exports.docx_exporter import create_lesson_docx
from app.exports.ai_bundle import format_all_data_bundle, format_prompt_with_transcription


def test_srt_timestamp_format():
    # 3723.456 seconds = 1 hour, 2 minutes, 3.456 seconds -> 01:02:03,456
    srt_ts = format_timestamp_srt(3723.456)
    assert srt_ts == "01:02:03,456"

    vtt_ts = format_timestamp_vtt(3723.456)
    assert vtt_ts == "01:02:03.456"


def test_export_to_srt_and_vtt():
    segments = [
        {"id": 0, "start": 1.0, "end": 4.5, "text": "Dzień dobry."},
        {"id": 1, "start": 5.0, "end": 10.2, "text": "Zaczynamy lekcję fizyki."}
    ]

    srt = export_to_srt(segments)
    assert "1\n00:00:01,000 --> 00:00:04,500\nDzień dobry." in srt
    assert "2\n00:00:05,000 --> 00:00:10,200\nZaczynamy lekcję fizyki." in srt

    vtt = export_to_vtt(segments)
    assert vtt.startswith("WEBVTT")
    assert "00:00:01.000 --> 00:00:04.500" in vtt


def test_create_lesson_docx():
    stream = create_lesson_docx(
        title="Funkcja Liniowa",
        subject="Matematyka",
        lesson_date="2026-09-03",
        notes_markdown="# Temat: Funkcja Liniowa\n\n## Najważniejsze informacje\n- Wzór: y = ax + b",
        events=[{"title": "Sprawdzian", "date": "2026-09-17", "type": "test", "description": "Z funkcji"}],
        transcription="Oto transkrypcja lekcji."
    )
    assert isinstance(stream, io.BytesIO)
    bytes_data = stream.getvalue()
    # Word docx files are zip files starting with PK magic bytes
    assert bytes_data.startswith(b"PK\x03\x04")
    assert len(bytes_data) > 1000


def test_format_all_data_bundle():
    bundle = format_all_data_bundle(
        topic="Historia Polski",
        subject="Historia",
        lesson_date="2026-09-03",
        notes="Główna notatka.",
        summary="Krótkie podsumowanie.",
        events=[{"title": "Sprawdzian", "date": "2026-09-17", "type": "test", "description": "Rozdział 1"}],
        transcription="Pełna transkrypcja lekcji."
    )
    assert "HISTORIA POLSKI" in bundle.upper()
    assert "NOTATKA GŁÓWNA" in bundle
    assert "PODSUMOWANIE" in bundle
    assert "ZAPOWIEDZIANE WYDARZENIA" in bundle
    assert "PEŁNA ORYGINALNA TRANSKRYPCJA" in bundle
