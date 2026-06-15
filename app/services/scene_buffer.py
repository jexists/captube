from __future__ import annotations

from dataclasses import dataclass

from app.services.image_diff import image_difference_score, visual_information_score


@dataclass(frozen=True)
class SceneCandidate:
    timestamp_seconds: int
    image_bytes: bytes


@dataclass(frozen=True)
class SceneDecision:
    candidate: SceneCandidate
    replace_previous: bool = False


class StableSceneBuffer:
    def __init__(
        self,
        stable_seconds: float = 2.0,
        max_pending_seconds: float = 5.0,
        scene_change_threshold: float = 28.0,
    ) -> None:
        self.stable_seconds = stable_seconds
        self.max_pending_seconds = max_pending_seconds
        self.scene_change_threshold = scene_change_threshold
        self.pending: SceneCandidate | None = None
        self.pending_first_seen: float | None = None
        self.pending_stable_since: float | None = None
        self.last_saved: SceneCandidate | None = None

    def observe(self, timestamp_seconds: int, image_bytes: bytes, clock_seconds: float) -> list[SceneDecision]:
        current = SceneCandidate(timestamp_seconds=timestamp_seconds, image_bytes=image_bytes)

        if self.pending is None:
            self._set_pending(current, clock_seconds, reset_first_seen=True)
            return []

        if _frames_are_similar(self.pending.image_bytes, image_bytes):
            if self._stable_age(clock_seconds) >= self.stable_seconds:
                return [self._mark_saved(self.pending)]
            return []

        if _is_probable_build_up(self.pending.image_bytes, image_bytes):
            self._set_pending(current, clock_seconds, reset_first_seen=False)
            if self._total_pending_age(clock_seconds) >= self.max_pending_seconds:
                return [self._mark_saved(current)]
            return []

        decisions = [self._mark_saved(self.pending)]
        self._set_pending(current, clock_seconds, reset_first_seen=True)
        return decisions

    def flush(self) -> list[SceneDecision]:
        if self.pending is None:
            return []
        return [self._mark_saved(self.pending)]

    def _set_pending(
        self,
        candidate: SceneCandidate,
        clock_seconds: float,
        reset_first_seen: bool,
    ) -> None:
        self.pending = candidate
        self.pending_stable_since = clock_seconds
        if reset_first_seen or self.pending_first_seen is None:
            self.pending_first_seen = clock_seconds

    def _stable_age(self, clock_seconds: float) -> float:
        if self.pending_stable_since is None:
            return 0
        return clock_seconds - self.pending_stable_since

    def _total_pending_age(self, clock_seconds: float) -> float:
        if self.pending_first_seen is None:
            return 0
        return clock_seconds - self.pending_first_seen

    def _mark_saved(self, candidate: SceneCandidate) -> SceneDecision:
        replace_previous = (
            self.last_saved is not None
            and _is_probable_build_up(self.last_saved.image_bytes, candidate.image_bytes)
        )
        self.last_saved = candidate
        self.pending = None
        self.pending_first_seen = None
        self.pending_stable_since = None
        return SceneDecision(candidate=candidate, replace_previous=replace_previous)


def _frames_are_similar(previous_bytes: bytes, current_bytes: bytes) -> bool:
    mean_delta, changed_ratio = image_difference_score(previous_bytes, current_bytes)
    return mean_delta < 4.0 or changed_ratio < 0.01


def _is_probable_build_up(previous_bytes: bytes, current_bytes: bytes) -> bool:
    mean_delta, changed_ratio = image_difference_score(previous_bytes, current_bytes)
    if mean_delta >= 45.0 or changed_ratio >= 0.55:
        return False
    return visual_information_score(current_bytes) >= visual_information_score(previous_bytes) + 0.005
