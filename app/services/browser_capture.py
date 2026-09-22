from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass
from pathlib import Path

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from app.config import (
    DEFAULT_CAPTURE_INTERVAL_SECONDS,
    DEFAULT_DIFF_THRESHOLD,
    DEFAULT_MIN_CHANGED_RATIO,
    DEFAULT_PLAYBACK_RATE,
)
from app.services.scene_buffer import SceneDecision, StableSceneBuffer


@dataclass(frozen=True)
class CapturedScene:
    image_path: Path
    timestamp_seconds: int


@dataclass(frozen=True)
class CaptureResult:
    scenes: list[CapturedScene]


async def capture_changed_scenes(
    url: str,
    output_dir: Path,
    playback_rate: float = DEFAULT_PLAYBACK_RATE,
    interval_seconds: float = DEFAULT_CAPTURE_INTERVAL_SECONDS,
    diff_threshold: float = DEFAULT_DIFF_THRESHOLD,
    min_changed_ratio: float = DEFAULT_MIN_CHANGED_RATIO,
    progress_callback=None,
    scene_callback=None,
) -> CaptureResult:
    image_dir = output_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    scenes: list[CapturedScene] = []
    scene_buffer = StableSceneBuffer()

    async with async_playwright() as playwright:
        await _progress(progress_callback, "Starting browser...", progress_percent=1)
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 720})
        try:
            await _progress(progress_callback, "Opening YouTube video...", progress_percent=2)
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await _try_accept_consent(page)
            video = page.locator("video").first
            try:
                await video.wait_for(state="attached", timeout=45000)
            except PlaywrightTimeoutError as exc:
                raise RuntimeError(
                    "YouTube video player was not found. The video may be unavailable, blocked, or requiring a login/verification page."
                ) from exc
            await _start_video(page, playback_rate)
            await _pause_video(page)

            await _progress(progress_callback, "Capturing changed scenes...", progress_percent=3)
            started_at = time.monotonic()
            playback = await _read_playback_state(page)
            duration = float(playback.get("duration") or 0)
            if duration <= 0:
                raise RuntimeError("The video duration could not be read.")

            sample_time = 0.0
            while sample_time < duration:
                await _seek_video(page, sample_time)
                current_bytes = await _screenshot_video_or_page(page)
                timestamp = max(0, int(sample_time))
                decisions = scene_buffer.observe(timestamp, current_bytes, sample_time)
                for decision in decisions:
                    scene = await _save_scene_decision(
                        decision,
                        image_dir,
                        scenes,
                        scene_callback,
                    )
                    if decision.replace_previous and len(scenes) >= 2:
                        await _progress(
                            progress_callback,
                            f"Updated scene {len(scenes)} after slide stabilized.",
                        )
                    else:
                        await _progress(
                            progress_callback,
                            f"Saved {len(scenes)} stabilized scenes.",
                        )

                progress_percent, eta_seconds = _estimate_seek_progress(
                    current_time=sample_time,
                    duration=duration,
                    started_at=started_at,
                    now=time.monotonic(),
                )
                await _progress(
                    progress_callback,
                    f"Capturing scenes... saved {len(scenes)} images.",
                    progress_percent=progress_percent,
                    eta_seconds=eta_seconds,
                )

                sample_time += max(interval_seconds, 0.25)
            for decision in scene_buffer.flush():
                await _save_scene_decision(decision, image_dir, scenes, scene_callback)
        finally:
            try:
                await browser.close()
            except Exception:
                pass

    return CaptureResult(scenes=scenes)


async def _save_scene_decision(
    decision: SceneDecision,
    image_dir: Path,
    scenes: list[CapturedScene],
    scene_callback,
) -> CapturedScene:
    if decision.replace_previous and scenes:
        previous = scenes.pop()
        try:
            previous.image_path.unlink(missing_ok=True)
        except OSError:
            pass

    scene_number = len(scenes) + 1
    timestamp = decision.candidate.timestamp_seconds
    image_path = image_dir / f"scene_{scene_number:04d}_{timestamp:06d}s.png"
    image_path.write_bytes(decision.candidate.image_bytes)
    scene = CapturedScene(image_path=image_path, timestamp_seconds=timestamp)
    scenes.append(scene)
    if scene_callback:
        await scene_callback(scene, decision.replace_previous)
    return scene


async def _progress(
    callback,
    message: str,
    progress_percent: int | None = None,
    eta_seconds: int | None = None,
) -> None:
    if callback:
        await callback(message, progress_percent, eta_seconds)


def _estimate_progress(playback: dict[str, float | bool], playback_rate: float) -> tuple[int, int | None]:
    duration = float(playback.get("duration") or 0)
    current_time = float(playback.get("current_time") or 0)
    if duration <= 0:
        return 3, None

    ratio = min(max(current_time / duration, 0), 1)
    progress_percent = min(99, max(3, math.floor(ratio * 100)))
    remaining_video_seconds = max(duration - current_time, 0)
    eta_seconds = math.ceil(remaining_video_seconds / max(playback_rate, 0.1))
    return progress_percent, eta_seconds


def _estimate_seek_progress(
    current_time: float,
    duration: float,
    started_at: float,
    now: float,
) -> tuple[int, int | None]:
    if duration <= 0:
        return 3, None

    ratio = min(max(current_time / duration, 0), 1)
    progress_percent = min(99, max(3, math.floor(ratio * 100)))
    if ratio <= 0:
        return progress_percent, None

    elapsed_seconds = max(now - started_at, 0)
    eta_seconds = math.ceil(elapsed_seconds * (1 - ratio) / ratio)
    return progress_percent, eta_seconds


async def _try_accept_consent(page) -> None:
    labels = [
        "Accept all",
        "Reject all",
        "I agree",
        "동의",
        "모두 수락",
        "모두 거부",
    ]
    for label in labels:
        try:
            button = page.get_by_role("button", name=label)
            if await button.count():
                await button.first.click(timeout=1500)
                await page.wait_for_timeout(1000)
                return
        except Exception:
            continue


async def _start_video(page, playback_rate: float) -> None:
    await page.evaluate(
        """async (rate) => {
            const video = document.querySelector('video');
            if (!video) return false;
            video.muted = true;
            video.playbackRate = rate;
            try {
                await video.play();
            } catch (error) {
                return false;
            }
            return true;
        }""",
        playback_rate,
    )
    await page.wait_for_timeout(1000)


async def _pause_video(page) -> None:
    await page.evaluate(
        """() => {
            const video = document.querySelector('video');
            if (!video) return false;
            video.pause();
            return true;
        }"""
    )
    await page.wait_for_timeout(250)


async def _seek_video(page, timestamp_seconds: float) -> None:
    target = await page.evaluate(
        """(timestamp) => {
            const video = document.querySelector('video');
            if (!video) return timestamp;

            const target = Math.min(Math.max(timestamp, 0), Number.isFinite(video.duration) ? video.duration : timestamp);
            video.currentTime = target;
            return target;
        }""",
        timestamp_seconds,
    )
    try:
        await page.wait_for_function(
            """(target) => {
                const video = document.querySelector('video');
                return video && Math.abs(video.currentTime - target) < 0.35 && video.readyState >= 2;
            }""",
            arg=target,
            timeout=800,
        )
    except PlaywrightTimeoutError:
        pass
    await page.wait_for_timeout(50)


async def _read_playback_state(page) -> dict[str, float | bool]:
    return await page.evaluate(
        """() => {
            const video = document.querySelector('video');
            if (!video) return { current_time: 0, duration: 0, ended: true, paused: true };
            return {
                current_time: Number.isFinite(video.currentTime) ? video.currentTime : 0,
                duration: Number.isFinite(video.duration) ? video.duration : 0,
                ended: video.ended,
                paused: video.paused
            };
        }"""
    )


async def _screenshot_video_or_page(page) -> bytes:
    try:
        return await page.locator("video").first.screenshot(timeout=5000)
    except PlaywrightTimeoutError:
        return await page.screenshot(full_page=False)
    except Exception:
        return await page.screenshot(full_page=False)
