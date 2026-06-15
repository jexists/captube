from __future__ import annotations

from urllib.parse import parse_qs, urlparse


def normalize_youtube_url(url: str) -> str:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()

    video_id = _extract_youtube_video_id(parsed.path, parse_qs(parsed.query), hostname)
    if not video_id:
        return url

    return f"https://www.youtube.com/watch?v={video_id}"


def _extract_youtube_video_id(path: str, query: dict[str, list[str]], hostname: str) -> str | None:
    if hostname in {"youtu.be", "www.youtu.be"}:
        return _first_path_part(path)

    if hostname not in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
        return None

    if path == "/watch":
        return _first_query_value(query, "v")

    for prefix in ("/shorts/", "/embed/", "/live/"):
        if path.startswith(prefix):
            return _first_path_part(path.removeprefix(prefix))

    return None


def _first_query_value(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key) or []
    return values[0] if values and values[0] else None


def _first_path_part(path: str) -> str | None:
    cleaned = path.strip("/")
    if not cleaned:
        return None
    return cleaned.split("/")[0]
