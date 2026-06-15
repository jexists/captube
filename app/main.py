from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import OUTPUT_DIR, STATIC_DIR, SUBTITLE_LANGUAGE_OPTIONS, TEMPLATE_DIR
from app.jobs import job_manager
from app.models import CreateJobRequest, CreateJobResponse, JobSnapshot
from app.services.urls import normalize_youtube_url

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="YouTube Study")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")
templates = Jinja2Templates(directory=TEMPLATE_DIR)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "language_options": SUBTITLE_LANGUAGE_OPTIONS,
        },
    )


@app.post("/api/jobs", response_model=CreateJobResponse)
async def create_job(payload: CreateJobRequest):
    languages = _normalize_languages(payload.subtitle_languages)
    normalized_url = normalize_youtube_url(str(payload.url))
    job = await job_manager.create_job(normalized_url, languages)
    return CreateJobResponse(job_id=job.job_id, status=job.status)


@app.get("/api/jobs/{job_id}", response_model=JobSnapshot)
async def get_job(job_id: str):
    job = await job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.snapshot()


def _normalize_languages(languages: list[str]) -> list[str]:
    allowed = set(SUBTITLE_LANGUAGE_OPTIONS)
    selected = []
    for language in languages:
        if language in allowed and language not in selected:
            selected.append(language)
    if not selected:
        selected.append("ko")
    return selected
