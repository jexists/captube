from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from app.config import OUTPUT_DIR
from app.models import JobSnapshot, JobStatus, SceneResult, SubtitleResult
from app.services.browser_capture import CapturedScene, capture_changed_scenes
from app.services.subtitles import (
    SubtitleFailure,
    SubtitleFile,
    SubtitleSegment,
    caption_for_timestamp,
    extract_subtitles_to_markdown,
)


@dataclass
class Job:
    job_id: str
    url: str
    subtitle_languages: list[str]
    status: JobStatus = JobStatus.QUEUED
    message: str = "Queued"
    progress_percent: int = 0
    elapsed_seconds: int = 0
    eta_seconds: int | None = None
    started_at: float | None = None
    image_urls: list[str] = field(default_factory=list)
    scenes: list[SceneResult] = field(default_factory=list)
    subtitles: list[SubtitleResult] = field(default_factory=list)
    subtitle_segments_by_language: dict[str, list[SubtitleSegment]] = field(default_factory=dict)
    error: str | None = None

    @property
    def output_dir(self) -> Path:
        return OUTPUT_DIR / self.job_id

    def snapshot(self) -> JobSnapshot:
        return JobSnapshot(
            job_id=self.job_id,
            status=self.status,
            message=self.message,
            progress_percent=self.progress_percent,
            elapsed_seconds=self.elapsed_seconds,
            eta_seconds=self.eta_seconds,
            image_urls=self.image_urls,
            scenes=self.scenes,
            subtitles=self.subtitles,
            error=self.error,
        )


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = asyncio.Lock()

    async def create_job(self, url: str, subtitle_languages: list[str]) -> Job:
        job = Job(
            job_id=uuid.uuid4().hex[:12],
            url=url,
            subtitle_languages=subtitle_languages,
        )
        async with self._lock:
            self._jobs[job.job_id] = job
        asyncio.create_task(self._run_job(job))
        return job

    async def get_job(self, job_id: str) -> Job | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def _set_progress(
        self,
        job: Job,
        message: str,
        progress_percent: int | None = None,
        eta_seconds: int | None = None,
    ) -> None:
        async with self._lock:
            job.message = message
            if progress_percent is not None:
                job.progress_percent = min(max(progress_percent, 0), 100)
            job.eta_seconds = eta_seconds
            if job.started_at is not None:
                job.elapsed_seconds = int(time.monotonic() - job.started_at)

    async def _run_job(self, job: Job) -> None:
        async with self._lock:
            job.status = JobStatus.RUNNING
            job.message = "Starting analysis..."
            job.progress_percent = 0
            job.eta_seconds = None
            job.elapsed_seconds = 0
            job.started_at = time.monotonic()

        try:
            job.output_dir.mkdir(parents=True, exist_ok=True)

            async def progress(
                message: str,
                progress_percent: int | None = None,
                eta_seconds: int | None = None,
            ) -> None:
                await self._set_progress(job, message, progress_percent, eta_seconds)

            async def scene_saved(scene: CapturedScene, replace_previous: bool) -> None:
                await self._add_scene(job, scene, replace_previous)

            loop = asyncio.get_running_loop()

            def subtitle_result(result: SubtitleFile | None, failure: SubtitleFailure | None) -> None:
                loop.call_soon_threadsafe(
                    asyncio.create_task,
                    self._add_subtitle_result(job, result, failure),
                )

            subtitle_task = self._extract_subtitles_for_job(job, subtitle_result)
            capture_task = self._capture_scenes_for_job(
                job,
                loop,
                progress,
                scene_saved,
            )

            capture_result, subtitle_result = await asyncio.gather(capture_task, subtitle_task)
            subtitle_files, subtitle_failures = subtitle_result
            await self._sync_subtitle_results(job, subtitle_files, subtitle_failures)

            async with self._lock:
                job.status = JobStatus.COMPLETED
                job.message = f"Completed. Saved {len(job.image_urls)} changed scenes."
                job.progress_percent = 100
                job.eta_seconds = 0
                if job.started_at is not None:
                    job.elapsed_seconds = int(time.monotonic() - job.started_at)
        except Exception as exc:
            async with self._lock:
                job.status = JobStatus.FAILED
                job.message = "Analysis failed."
                job.error = _format_exception(exc)
                job.eta_seconds = None
                if job.started_at is not None:
                    job.elapsed_seconds = int(time.monotonic() - job.started_at)

    async def _extract_subtitles_for_job(
        self,
        job: Job,
        result_callback,
    ) -> tuple[list[SubtitleFile], list[SubtitleFailure]]:
        try:
            return await asyncio.to_thread(
                extract_subtitles_to_markdown,
                job.url,
                job.subtitle_languages,
                job.output_dir,
                result_callback,
            )
        except Exception as exc:
            failures = [
                SubtitleFailure(language=language, error=str(exc))
                for language in job.subtitle_languages
            ]
            for failure in failures:
                result_callback(None, failure)
            return [], failures

    async def _capture_scenes_for_job(
        self,
        job: Job,
        loop: asyncio.AbstractEventLoop,
        progress_callback,
        scene_callback,
    ) -> object:
        def run_capture() -> object:
            async def progress_from_capture(
                message: str,
                progress_percent: int | None = None,
                eta_seconds: int | None = None,
            ) -> None:
                future = asyncio.run_coroutine_threadsafe(
                    progress_callback(message, progress_percent, eta_seconds),
                    loop,
                )
                await asyncio.wrap_future(future)

            async def scene_from_capture(scene: CapturedScene, replace_previous: bool) -> None:
                future = asyncio.run_coroutine_threadsafe(
                    scene_callback(scene, replace_previous),
                    loop,
                )
                await asyncio.wrap_future(future)

            return asyncio.run(
                capture_changed_scenes(
                    job.url,
                    job.output_dir,
                    progress_callback=progress_from_capture,
                    scene_callback=scene_from_capture,
                )
            )

        return await asyncio.to_thread(run_capture)

    async def _add_scene(self, job: Job, scene: CapturedScene, replace_previous: bool) -> None:
        scene_result = SceneResult(
            image_url=f"/outputs/{job.job_id}/images/{scene.image_path.name}",
            timestamp_seconds=scene.timestamp_seconds,
            captions_by_language=self._captions_for_job(job, scene.timestamp_seconds),
        )
        async with self._lock:
            if replace_previous and job.scenes:
                job.scenes.pop()
                job.image_urls.pop()
            job.scenes.append(scene_result)
            job.image_urls.append(scene_result.image_url)

    async def _add_subtitle_result(
        self,
        job: Job,
        result: SubtitleFile | None,
        failure: SubtitleFailure | None,
    ) -> None:
        async with self._lock:
            if result is not None:
                job.subtitle_segments_by_language[result.language] = result.segments
                self._upsert_subtitle(
                    job,
                    SubtitleResult(
                        language=result.language,
                        url=f"/outputs/{job.job_id}/subtitles/{result.path.name}",
                    ),
                )
                self._refresh_scene_captions(job, result.language)
            if failure is not None:
                self._upsert_subtitle(
                    job,
                    SubtitleResult(language=failure.language, error=failure.error),
                )

    async def _sync_subtitle_results(
        self,
        job: Job,
        subtitle_files: list[SubtitleFile],
        subtitle_failures: list[SubtitleFailure],
    ) -> None:
        for result in subtitle_files:
            await self._add_subtitle_result(job, result, None)
        for failure in subtitle_failures:
            await self._add_subtitle_result(job, None, failure)

    def _captions_for_job(self, job: Job, timestamp_seconds: int) -> dict[str, str]:
        return {
            language: caption_for_timestamp(
                job.subtitle_segments_by_language.get(language, []),
                timestamp_seconds,
            )
            for language in job.subtitle_languages
        }

    def _refresh_scene_captions(self, job: Job, language: str) -> None:
        segments = job.subtitle_segments_by_language.get(language, [])
        for scene in job.scenes:
            scene.captions_by_language[language] = caption_for_timestamp(
                segments,
                scene.timestamp_seconds,
            )

    def _upsert_subtitle(self, job: Job, subtitle: SubtitleResult) -> None:
        job.subtitles = [item for item in job.subtitles if item.language != subtitle.language]
        job.subtitles.append(subtitle)


job_manager = JobManager()


def _format_exception(exc: Exception) -> str:
    message = str(exc).strip()
    exc_type = type(exc).__name__
    if message:
        return f"{exc_type}: {message}"
    cause = exc.__cause__ or exc.__context__
    if cause is not None:
        cause_message = str(cause).strip()
        cause_type = type(cause).__name__
        if cause_message:
            return f"{exc_type}: caused by {cause_type}: {cause_message}"
        return f"{exc_type}: caused by {cause_type}"
    return exc_type
