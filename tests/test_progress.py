from app.services.browser_capture import _estimate_progress, _estimate_seek_progress


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


def test_estimate_seek_progress_uses_actual_processing_rate():
    progress, eta = _estimate_seek_progress(
        current_time=250,
        duration=1000,
        started_at=10,
        now=40,
    )

    assert progress == 25
    assert eta == 90


def test_estimate_seek_progress_before_first_sample_has_unknown_eta():
    progress, eta = _estimate_seek_progress(
        current_time=0,
        duration=1000,
        started_at=10,
        now=40,
    )

    assert progress == 3
    assert eta is None
