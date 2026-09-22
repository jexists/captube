from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "outputs"
STATIC_DIR = Path(__file__).resolve().parent / "static"
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

DEFAULT_PLAYBACK_RATE = 2.0
DEFAULT_CAPTURE_INTERVAL_SECONDS = 15.0
DEFAULT_DIFF_THRESHOLD = 7.5
DEFAULT_MIN_CHANGED_RATIO = 0.02
SUBTITLE_LANGUAGE_OPTIONS = ["ko", "en", "ja", "auto"]
