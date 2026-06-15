from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


SubtitleLanguage = Literal["ko", "en", "ja", "auto"]


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class CreateJobRequest(BaseModel):
    url: HttpUrl
    subtitle_languages: list[SubtitleLanguage] = Field(default_factory=lambda: ["ko"])


class CreateJobResponse(BaseModel):
    job_id: str
    status: JobStatus


class SubtitleResult(BaseModel):
    language: str
    url: str | None = None
    error: str | None = None


class SceneResult(BaseModel):
    image_url: str
    timestamp_seconds: int
    captions_by_language: dict[str, str] = Field(default_factory=dict)


class JobSnapshot(BaseModel):
    job_id: str
    status: JobStatus
    message: str
    progress_percent: int = 0
    elapsed_seconds: int = 0
    eta_seconds: int | None = None
    image_urls: list[str] = Field(default_factory=list)
    scenes: list[SceneResult] = Field(default_factory=list)
    subtitles: list[SubtitleResult] = Field(default_factory=list)
    error: str | None = None
