from io import BytesIO

from PIL import Image, ImageChops, ImageStat


def _prepare_image(image_bytes: bytes, size: tuple[int, int] = (160, 90)) -> Image.Image:
    image = Image.open(BytesIO(image_bytes))
    return image.convert("L").resize(size)


def image_difference_score(previous_bytes: bytes, current_bytes: bytes) -> tuple[float, float]:
    previous = _prepare_image(previous_bytes)
    current = _prepare_image(current_bytes)
    diff = ImageChops.difference(previous, current)
    stat = ImageStat.Stat(diff)
    mean_delta = float(stat.mean[0])
    histogram = diff.histogram()
    changed_pixels = sum(count for value, count in enumerate(histogram) if value > 18)
    changed_ratio = changed_pixels / float(diff.width * diff.height)
    return mean_delta, changed_ratio


def should_save_frame(
    previous_bytes: bytes | None,
    current_bytes: bytes,
    diff_threshold: float = 7.5,
    min_changed_ratio: float = 0.02,
) -> bool:
    if previous_bytes is None:
        return True

    mean_delta, changed_ratio = image_difference_score(previous_bytes, current_bytes)
    return mean_delta >= diff_threshold and changed_ratio >= min_changed_ratio


def visual_information_score(image_bytes: bytes) -> float:
    image = _prepare_image(image_bytes)
    histogram = image.histogram()
    total_pixels = image.width * image.height
    non_white_pixels = sum(count for value, count in enumerate(histogram) if value < 245)
    return non_white_pixels / float(total_pixels)
