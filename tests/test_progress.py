from app.services.browser_capture import _estimate_progress


def test_estimate_progress_uses_video_time_and_playback_rate():
    progress, eta = _estimate_progress(
        {"current_time": 50, "duration": 100, "ended": False, "paused": False},
        playback_rate=2.0,
    )

    assert progress == 50
    assert eta == 25


def test_estimate_progress_without_duration_has_unknown_eta():
    progress, eta = _estimate_progress(
        {"current_time": 0, "duration": 0, "ended": False, "paused": False},
        playback_rate=2.0,
    )

    assert progress == 3
    assert eta is None
