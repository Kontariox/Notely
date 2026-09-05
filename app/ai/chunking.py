import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from app.transcription.base import TranscriptionSegment


@dataclass
class TranscriptionChunk:
    index: int
    total: int
    start_time: float
    end_time: float
    text: str
    segments: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def time_range_str(self) -> str:
        s_min, s_sec = int(self.start_time // 60), int(self.start_time % 60)
        e_min, e_sec = int(self.end_time // 60), int(self.end_time % 60)
        return f"{s_min:02d}:{s_sec:02d} - {e_min:02d}:{e_sec:02d}"


def chunk_segments(
    segments: List[TranscriptionSegment],
    max_chunk_chars: int = 5000,
    overlap_segments: int = 1
) -> List[TranscriptionChunk]:
    """
    Chunks a list of transcription segments into coherent blocks respecting
    segment boundaries and natural speech breaks.
    """
    if not segments:
        return []

    chunks_raw: List[List[TranscriptionSegment]] = []
    current_chunk: List[TranscriptionSegment] = []
    current_length = 0

    for seg in segments:
        seg_len = len(seg.text)
        if current_chunk and (current_length + seg_len > max_chunk_chars):
            chunks_raw.append(list(current_chunk))
            # Start new chunk with overlap if specified
            if overlap_segments > 0 and len(current_chunk) >= overlap_segments:
                current_chunk = current_chunk[-overlap_segments:]
                current_length = sum(len(s.text) for s in current_chunk)
            else:
                current_chunk = []
                current_length = 0

        current_chunk.append(seg)
        current_length += seg_len

    if current_chunk:
        chunks_raw.append(current_chunk)

    total_chunks = len(chunks_raw)
    result: List[TranscriptionChunk] = []

    for i, chunk_segs in enumerate(chunks_raw):
        start_t = chunk_segs[0].start if chunk_segs else 0.0
        end_t = chunk_segs[-1].end if chunk_segs else 0.0
        chunk_text = " ".join(s.text for s in chunk_segs)
        result.append(
            TranscriptionChunk(
                index=i + 1,
                total=total_chunks,
                start_time=start_t,
                end_time=end_t,
                text=chunk_text,
                segments=[s.to_dict() for s in chunk_segs]
            )
        )

    return result


def chunk_plain_text(
    text: str,
    max_chunk_chars: int = 4000
) -> List[str]:
    """
    Splits plain text into natural parts avoiding cutoffs in the middle of sentences.
    Prefers splitting on paragraphs, then sentences.
    """
    text = text.strip()
    if not text:
        return []

    if len(text) <= max_chunk_chars:
        return [text]

    # Split by paragraphs first
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: List[str] = []
    current_block: List[str] = []
    current_len = 0

    for p in paragraphs:
        if len(p) > max_chunk_chars:
            # Paragraph is too long; split by sentences
            sentences = re.split(r'(?<=[.?!])\s+', p)
            for s in sentences:
                s = s.strip()
                if not s:
                    continue
                if current_len + len(s) > max_chunk_chars and current_block:
                    chunks.append(" ".join(current_block))
                    current_block = []
                    current_len = 0
                current_block.append(s)
                current_len += len(s) + 1
        else:
            if current_len + len(p) > max_chunk_chars and current_block:
                chunks.append("\n\n".join(current_block))
                current_block = []
                current_len = 0
            current_block.append(p)
            current_len += len(p) + 2

    if current_block:
        chunks.append("\n\n".join(current_block))

    return chunks


def format_external_ai_parts(text: str, max_chars_per_part: int = 4000) -> List[str]:
    """
    Splits text into labelled parts suitable for pasting into external LLMs.
    Includes headers like '--- CZĘŚĆ 1/3 ---' and navigation cues.
    """
    raw_parts = chunk_plain_text(text, max_chunk_chars=max_chars_per_part)
    total = len(raw_parts)

    formatted: List[str] = []
    for idx, part in enumerate(raw_parts, start=1):
        header = f"[CZĘŚĆ {idx}/{total} - MATERIAŁ Z LEKCJI]\n"
        footer = ""
        if idx < total:
            footer = f"\n\n(Ciąg dalszy w Części {idx+1}/{total}...)"
        else:
            footer = f"\n\n(Koniec materiału - Część {total}/{total})"
        formatted.append(f"{header}\n{part}{footer}")

    return formatted
