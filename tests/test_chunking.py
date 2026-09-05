import pytest
from app.transcription.base import TranscriptionSegment
from app.ai.chunking import chunk_segments, chunk_plain_text, format_external_ai_parts
from tests.fixtures.sample_transcripts import SAMPLE_HISTORY_TRANSCRIPTION


def test_chunk_segments_basic():
    segments = [
        TranscriptionSegment(id=0, start=0.0, end=4.5, text="Dzień dobry wszystkim."),
        TranscriptionSegment(id=1, start=4.5, end=9.0, text="Dzisiaj omawiamy historię Polski."),
        TranscriptionSegment(id=2, start=9.0, end=15.0, text="11 listopada 1918 roku to ważna data."),
        TranscriptionSegment(id=3, start=15.0, end=22.0, text="Józef Piłsudski przejął naczelne dowództwo nad wojskiem."),
    ]

    # Chunk with small max_chunk_chars to force multiple chunks
    chunks = chunk_segments(segments, max_chunk_chars=60, overlap_segments=0)
    assert len(chunks) >= 2
    assert chunks[0].index == 1
    assert chunks[0].total == len(chunks)
    assert chunks[0].start_time == 0.0
    assert chunks[0].end_time > 0.0
    assert "Dzień dobry" in chunks[0].text


def test_chunk_segments_overlap():
    segments = [
        TranscriptionSegment(id=0, start=0.0, end=5.0, text="Część pierwsza wypowiedzi."),
        TranscriptionSegment(id=1, start=5.0, end=10.0, text="Część druga wypowiedzi."),
        TranscriptionSegment(id=2, start=10.0, end=15.0, text="Część trzecia wypowiedzi."),
        TranscriptionSegment(id=3, start=15.0, end=20.0, text="Część czwarta wypowiedzi."),
    ]

    chunks = chunk_segments(segments, max_chunk_chars=55, overlap_segments=1)
    assert len(chunks) > 1
    # Check that overlap segment appears in subsequent chunk
    assert len(chunks[1].segments) >= 2


def test_chunk_plain_text_sentences():
    text = (
        "Pierwsze zdanie testowe. Drugie bardzo długie zdanie testowe. "
        "Trzecie zdanie z pytaniem? Czwarte zdanie z wykrzyknikiem!"
    )
    chunks = chunk_plain_text(text, max_chunk_chars=60)
    assert len(chunks) >= 2
    # Ensure no sentence was broken in half
    for chunk in chunks:
        assert chunk[-1] in (".", "!", "?")


def test_format_external_ai_parts():
    parts = format_external_ai_parts(SAMPLE_HISTORY_TRANSCRIPTION, max_chars_per_part=250)
    assert len(parts) >= 2
    assert "[CZĘŚĆ 1/" in parts[0]
    assert "Część 1/" in parts[0] or "Części 2/" in parts[0]
    assert f"Część {len(parts)}/{len(parts)}" in parts[-1]
