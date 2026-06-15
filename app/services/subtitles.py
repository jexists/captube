from __future__ import annotations

import html
import json
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL


@dataclass(frozen=True)
class SubtitleFile:
    language: str
    path: Path
    segments: list["SubtitleSegment"]


@dataclass(frozen=True)
class SubtitleFailure:
    language: str
    error: str


@dataclass(frozen=True)
class SubtitleSegment:
    start_seconds: float
    end_seconds: float
    text: str


def subtitle_path(output_dir: Path, language: str) -> Path:
    return output_dir / "subtitles" / f"subtitle.{language}.md"


def extract_subtitles_to_markdown(
    url: str,
    languages: list[str],
    output_dir: Path,
    result_callback=None,
) -> tuple[list[SubtitleFile], list[SubtitleFailure]]:
    subtitle_dir = output_dir / "subtitles"
    subtitle_dir.mkdir(parents=True, exist_ok=True)

    info = _extract_video_info(url)
    results: list[SubtitleFile] = []
    failures: list[SubtitleFailure] = []

    for language in languages:
        try:
            caption = _select_caption(info, language)
            raw_caption = _download_text(caption["url"])
            segments = caption_text_to_segments(raw_caption)
            markdown = caption_text_to_markdown(
                raw_caption,
                title=info.get("title") or "YouTube subtitle",
                language=caption["language"],
            )
            output_path = subtitle_path(output_dir, language)
            output_path.write_text(markdown, encoding="utf-8")
            result = SubtitleFile(language=language, path=output_path, segments=segments)
            results.append(result)
            if result_callback:
                result_callback(result, None)
        except Exception as exc:
            failure = SubtitleFailure(language=language, error=str(exc))
            failures.append(failure)
            if result_callback:
                result_callback(None, failure)

    return results, failures


def caption_text_to_markdown(raw_caption: str, title: str, language: str) -> str:
    segments = caption_text_to_segments(raw_caption)
    body = "\n\n".join(
        f"- [{_format_timestamp(segment.start_seconds)}] {segment.text}" for segment in segments
    )
    if not body:
        body = "_No subtitle text was found._"

    return f"# {title}\n\nLanguage: `{language}`\n\n{body}\n"


def caption_text_to_segments(raw_caption: str) -> list[SubtitleSegment]:
    stripped = raw_caption.lstrip()
    if stripped.startswith("{"):
        return _json3_to_segments(stripped)
    return _webvtt_to_segments(raw_caption)


def captions_for_timestamp(
    segments_by_language: dict[str, list[SubtitleSegment]],
    timestamp_seconds: float,
) -> dict[str, str]:
    return {
        language: caption_for_timestamp(segments, timestamp_seconds)
        for language, segments in segments_by_language.items()
    }


def caption_for_timestamp(segments: list[SubtitleSegment], timestamp_seconds: float) -> str:
    matches = [
        segment.text
        for segment in segments
        if segment.start_seconds <= timestamp_seconds <= segment.end_seconds
    ]
    return " ".join(_dedupe_adjacent(matches))


def _extract_video_info(url: str) -> dict[str, Any]:
    options = {
        "quiet": True,
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
    }
    with YoutubeDL(options) as ydl:
        return ydl.extract_info(url, download=False)


def _select_caption(info: dict[str, Any], requested_language: str) -> dict[str, str]:
    subtitles = info.get("subtitles") or {}
    automatic = info.get("automatic_captions") or {}

    if requested_language == "auto":
        for language in ("ko", "en", "ja"):
            caption = _find_caption(automatic, language)
            if caption:
                caption["language"] = language
                return caption
        for language in sorted(automatic.keys()):
            caption = _find_caption(automatic, language)
            if caption:
                caption["language"] = language
                return caption
        raise ValueError("No automatic captions are available.")

    caption = _find_caption(subtitles, requested_language)
    if caption:
        caption["language"] = requested_language
        return caption

    caption = _find_caption(automatic, requested_language)
    if caption:
        caption["language"] = requested_language
        return caption

    raise ValueError(f"No subtitles found for language '{requested_language}'.")


def _find_caption(captions: dict[str, list[dict[str, Any]]], language: str) -> dict[str, str] | None:
    candidates = captions.get(language) or []
    if not candidates:
        return None

    for preferred_ext in ("vtt", "json3", "srv3", "ttml"):
        for candidate in candidates:
            if candidate.get("url") and candidate.get("ext") == preferred_ext:
                return {"url": candidate["url"], "ext": preferred_ext}

    first = candidates[0]
    if first.get("url"):
        return {"url": first["url"], "ext": str(first.get("ext") or "unknown")}
    return None


def _download_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def _json3_to_segments(raw_caption: str) -> list[SubtitleSegment]:
    data = json.loads(raw_caption)
    segments: list[SubtitleSegment] = []
    for event in data.get("events", []):
        event_segments = event.get("segs") or []
        text = "".join(segment.get("utf8", "") for segment in event_segments)
        text = _clean_caption_line(text)
        start_ms = float(event.get("tStartMs") or 0)
        duration_ms = float(event.get("dDurationMs") or 0)
        if text:
            start_seconds = start_ms / 1000
            end_seconds = (start_ms + max(duration_ms, 1)) / 1000
            segments.append(SubtitleSegment(start_seconds, end_seconds, text))
    return _dedupe_adjacent_segments(segments)


def _webvtt_to_segments(raw_caption: str) -> list[SubtitleSegment]:
    segments: list[SubtitleSegment] = []
    current_start: float | None = None
    current_end: float | None = None
    current_lines: list[str] = []

    def flush_current() -> None:
        nonlocal current_start, current_end, current_lines
        if current_start is None or current_end is None:
            current_lines = []
            return
        text = _clean_caption_line(" ".join(current_lines))
        if text:
            segments.append(SubtitleSegment(current_start, current_end, text))
        current_start = None
        current_end = None
        current_lines = []

    for raw_line in raw_caption.splitlines():
        line = raw_line.strip()
        if "-->" in line:
            flush_current()
            start_text, end_text = line.split("-->", 1)
            current_start = _parse_timestamp(start_text.strip())
            current_end = _parse_timestamp(end_text.strip().split(" ")[0])
            continue

        if not line:
            flush_current()
            continue

        if line == "WEBVTT" or line.startswith("Kind:") or line.startswith("Language:"):
            continue
        if re.fullmatch(r"\d+", line):
            continue
        if current_start is not None and current_end is not None:
            current_lines.append(line)

    flush_current()
    return _dedupe_adjacent_segments(segments)


def _parse_timestamp(value: str) -> float:
    match = re.match(r"(?:(\d+):)?(\d+):(\d+(?:\.\d+)?)", value)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2))
    seconds = float(match.group(3))
    return hours * 3600 + minutes * 60 + seconds


def _format_timestamp(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    minutes, second = divmod(total_seconds, 60)
    hour, minute = divmod(minutes, 60)
    if hour:
        return f"{hour:02d}:{minute:02d}:{second:02d}"
    return f"{minute:02d}:{second:02d}"


def _webvtt_to_lines(raw_caption: str) -> list[str]:
    lines: list[str] = []
    for line in raw_caption.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        if cleaned == "WEBVTT" or cleaned.startswith("Kind:") or cleaned.startswith("Language:"):
            continue
        if "-->" in cleaned:
            continue
        if re.fullmatch(r"\d+", cleaned):
            continue
        cleaned = _clean_caption_line(cleaned)
        if cleaned:
            lines.append(cleaned)
    return _dedupe_adjacent(lines)


def _clean_caption_line(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _dedupe_adjacent(lines: list[str]) -> list[str]:
    deduped: list[str] = []
    for line in lines:
        if not deduped or deduped[-1] != line:
            deduped.append(line)
    return deduped


def _dedupe_adjacent_segments(segments: list[SubtitleSegment]) -> list[SubtitleSegment]:
    deduped: list[SubtitleSegment] = []
    for segment in segments:
        if not deduped or deduped[-1].text != segment.text:
            deduped.append(segment)
    return deduped
