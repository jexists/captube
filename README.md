# YouTube Study

Local web app for capturing visually changed scenes from a YouTube video and saving selected subtitles as Markdown files.

## Setup

```bash
uv sync
uv run playwright install chromium
```

## Run

```bash
uv run uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 and paste a YouTube URL.

## Notes

- The app is intended for local use.
- It does not save the source video file.
- Scene images and subtitle Markdown files are written under `outputs/{job_id}/`.
- Browser capture may fail for videos that require login, age verification, unusual consent flows, or blocked autoplay.
