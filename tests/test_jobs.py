from app.jobs import Job
from app.models import JobStatus, SceneResult, SubtitleResult


def test_job_snapshot_contains_partial_subtitle_failure():
    job = Job(job_id="abc", url="https://example.com", subtitle_languages=["ko", "en"])
    job.status = JobStatus.COMPLETED
    job.progress_percent = 100
    job.elapsed_seconds = 42
    job.eta_seconds = 0
    job.image_urls = ["/outputs/abc/images/scene.png"]
    job.scenes = [
        SceneResult(
            image_url="/outputs/abc/images/scene.png",
            timestamp_seconds=12,
            captions_by_language={"ko": "안녕하세요", "en": "Hello"},
        )
    ]
    job.subtitles = [
        SubtitleResult(language="ko", url="/outputs/abc/subtitles/subtitle.ko.md"),
        SubtitleResult(language="en", error="No subtitles found for language 'en'."),
    ]

    snapshot = job.snapshot()

    assert snapshot.status == JobStatus.COMPLETED
    assert snapshot.image_urls == ["/outputs/abc/images/scene.png"]
    assert snapshot.scenes[0].captions_by_language["ko"] == "안녕하세요"
    assert snapshot.subtitles[0].url.endswith("subtitle.ko.md")
    assert snapshot.subtitles[1].error
    assert snapshot.progress_percent == 100
    assert snapshot.elapsed_seconds == 42
    assert snapshot.eta_seconds == 0
