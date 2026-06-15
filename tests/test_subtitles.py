from pathlib import Path

from app.services.subtitles import (
    caption_for_timestamp,
    caption_text_to_markdown,
    caption_text_to_segments,
    captions_for_timestamp,
    subtitle_path,
)


def test_subtitle_path_uses_language_suffix(tmp_path: Path):
    assert subtitle_path(tmp_path, "ko") == tmp_path / "subtitles" / "subtitle.ko.md"


def test_webvtt_caption_converts_to_markdown():
    raw = """WEBVTT

00:00:00.000 --> 00:00:01.000
Hello <b>world</b>

00:00:01.000 --> 00:00:02.000
Hello <b>world</b>

00:00:02.000 --> 00:00:03.000
Next line
"""

    markdown = caption_text_to_markdown(raw, title="Demo", language="en")

    assert markdown.startswith("# Demo")
    assert "- [00:00] Hello world" in markdown
    assert markdown.count("Hello world") == 1
    assert "- [00:02] Next line" in markdown


def test_json3_caption_converts_to_markdown():
    raw = '{"events":[{"tStartMs":1000,"dDurationMs":1500,"segs":[{"utf8":"안녕 "},{"utf8":"세계"}]},{"tStartMs":3000,"dDurationMs":1000,"segs":[{"utf8":"다음"}]}]}'

    markdown = caption_text_to_markdown(raw, title="Demo", language="ko")

    assert "- [00:01] 안녕 세계" in markdown
    assert "- [00:03] 다음" in markdown


def test_webvtt_caption_segments_keep_timestamps():
    raw = """WEBVTT

00:00:05.000 --> 00:00:07.500
Timed line
"""

    segments = caption_text_to_segments(raw)

    assert segments[0].start_seconds == 5
    assert segments[0].end_seconds == 7.5
    assert segments[0].text == "Timed line"


def test_caption_for_timestamp_matches_only_overlapping_segment():
    raw = """WEBVTT

00:00:01.000 --> 00:00:02.000
First

00:00:04.000 --> 00:00:05.000
Second
"""

    segments = caption_text_to_segments(raw)

    assert caption_for_timestamp(segments, 1.5) == "First"
    assert caption_for_timestamp(segments, 3.0) == ""


def test_captions_for_timestamp_matches_multiple_languages():
    ko = caption_text_to_segments("WEBVTT\n\n00:00:01.000 --> 00:00:03.000\n안녕\n")
    en = caption_text_to_segments("WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHello\n")

    captions = captions_for_timestamp({"ko": ko, "en": en}, 2.0)

    assert captions == {"ko": "안녕", "en": "Hello"}
