from io import BytesIO

from PIL import Image

from app.services.image_diff import should_save_frame


def _png(color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (64, 36), color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_first_frame_is_saved():
    assert should_save_frame(None, _png((0, 0, 0)))


def test_same_frame_is_not_saved():
    frame = _png((24, 24, 24))
    assert not should_save_frame(frame, frame)


def test_changed_frame_is_saved():
    previous = _png((0, 0, 0))
    current = _png((255, 255, 255))
    assert should_save_frame(previous, current)
