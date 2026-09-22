import asyncio

import app.jobs as jobs_module
from app.jobs import Job
from app.services.browser_capture import CaptureResult
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


def test_job_completes_when_subtitle_info_lookup_fails(monkeypatch):
    async def fake_capture_changed_scenes(*args, **kwargs):
        progress_callback = kwargs.get("progress_callback")
        if progress_callback:
            await progress_callback("Captured test scenes.", 100, 0)
        return CaptureResult(scenes=[])

    def fake_extract_subtitles_to_markdown(*args, **kwargs):
        raise RuntimeError("subtitle lookup failed")

    monkeypatch.setattr(jobs_module, "capture_changed_scenes", fake_capture_changed_scenes)
    monkeypatch.setattr(
        jobs_module,
        "extract_subtitles_to_markdown",
        fake_extract_subtitles_to_markdown,
    )

    manager = jobs_module.JobManager()
    job = Job(
        job_id="subtitlefail",
        url="https://www.youtube.com/watch?v=zpMHGnSAusI",
        subtitle_languages=["ko", "en"],
    )

    asyncio.run(manager._run_job(job))

    assert job.status == JobStatus.COMPLETED
    assert job.error is None
    assert job.progress_percent == 100
    assert [subtitle.language for subtitle in job.subtitles] == ["ko", "en"]
    assert all(subtitle.error == "subtitle lookup failed" for subtitle in job.subtitles)
