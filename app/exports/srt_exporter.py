from typing import Any, Dict, List


def format_timestamp_srt(seconds: float) -> str:
    """Formats seconds to SRT format: HH:MM:SS,mmm"""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def format_timestamp_vtt(seconds: float) -> str:
    """Formats seconds to WebVTT format: HH:MM:SS.mmm"""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hrs:02d}:{mins:02d}:{secs:02d}.{millis:03d}"


def export_to_srt(segments: List[Dict[str, Any]]) -> str:
    """Generates standard SubRip (.srt) subtitle string from segments."""
    if not segments:
        return ""

    lines: List[str] = []
    for idx, seg in enumerate(segments, start=1):
        start_t = float(seg.get("start", 0.0))
        end_t = float(seg.get("end", 0.0))
        text = str(seg.get("text", "")).strip()

        lines.append(str(idx))
        lines.append(f"{format_timestamp_srt(start_t)} --> {format_timestamp_srt(end_t)}")
        lines.append(text)
        lines.append("")

    return "\n".join(lines)


def export_to_vtt(segments: List[Dict[str, Any]]) -> str:
    """Generates standard WebVTT (.vtt) subtitle string from segments."""
    lines: List[str] = ["WEBVTT", ""]
    for idx, seg in enumerate(segments, start=1):
        start_t = float(seg.get("start", 0.0))
        end_t = float(seg.get("end", 0.0))
        text = str(seg.get("text", "")).strip()

        lines.append(str(idx))
        lines.append(f"{format_timestamp_vtt(start_t)} --> {format_timestamp_vtt(end_t)}")
        lines.append(text)
        lines.append("")

    return "\n".join(lines)
