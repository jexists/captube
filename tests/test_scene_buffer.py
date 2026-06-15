from io import BytesIO

from PIL import Image, ImageDraw

from app.services.scene_buffer import StableSceneBuffer


def _slide(extra_blocks: int = 0, color: tuple[int, int, int] = (255, 255, 255)) -> bytes:
    image = Image.new("RGB", (320, 180), color)
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 150, 55), outline=(0, 45, 90), width=3)
    draw.text((30, 32), "RNN", fill=(0, 45, 90))
    for index in range(extra_blocks):
        x = 30 + index * 65
        draw.rectangle((x, 110, x + 42, 145), outline=(0, 45, 90), fill=(200, 230, 180), width=2)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_pending_scene_is_not_saved_until_stable():
    buffer = StableSceneBuffer(stable_seconds=2.0)
    first = _slide(extra_blocks=0)

    assert buffer.observe(1, first, clock_seconds=0) == []
    assert buffer.observe(2, first, clock_seconds=1.0) == []
    decisions = buffer.observe(3, first, clock_seconds=2.1)

    assert len(decisions) == 1
    assert decisions[0].candidate.timestamp_seconds == 1


def test_build_up_replaces_pending_with_latest_candidate():
    buffer = StableSceneBuffer(stable_seconds=2.0)
    partial = _slide(extra_blocks=0)
    complete = _slide(extra_blocks=4)

    assert buffer.observe(1, partial, clock_seconds=0) == []
    assert buffer.observe(2, complete, clock_seconds=1.0) == []
    decisions = buffer.observe(3, complete, clock_seconds=3.1)

    assert len(decisions) == 1
    assert decisions[0].candidate.timestamp_seconds == 2


def test_scene_change_flushes_pending_candidate():
    buffer = StableSceneBuffer(stable_seconds=2.0)
    first = _slide(extra_blocks=1)
    second = _slide(extra_blocks=1, color=(80, 100, 140))

    assert buffer.observe(1, first, clock_seconds=0) == []
    decisions = buffer.observe(5, second, clock_seconds=1.0)

    assert len(decisions) == 1
    assert decisions[0].candidate.timestamp_seconds == 1


def test_max_pending_time_forces_latest_candidate_save():
    buffer = StableSceneBuffer(stable_seconds=2.0, max_pending_seconds=5.0)
    partial = _slide(extra_blocks=0)
    complete = _slide(extra_blocks=4)

    assert buffer.observe(1, partial, clock_seconds=0) == []
    decisions = buffer.observe(6, complete, clock_seconds=5.1)

    assert len(decisions) == 1
    assert decisions[0].candidate.timestamp_seconds == 6
