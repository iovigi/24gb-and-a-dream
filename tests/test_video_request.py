"""ComfyUI's KSampler rejects a negative seed, but -1 is the UI's "random"."""

from __future__ import annotations

from pathlib import Path

from video.base import MAX_SEED, VideoGenerationRequest


def _request(seed: int) -> VideoGenerationRequest:
    return VideoGenerationRequest(
        prompt="a neon city", output_path=Path("scene.mp4"), duration_seconds=5.0,
        width=1280, height=704, fps=24, seed=seed,
    )


def test_explicit_seed_is_passed_through() -> None:
    assert _request(1234).resolved_seed() == 1234


def test_zero_is_a_valid_explicit_seed() -> None:
    assert _request(0).resolved_seed() == 0


def test_random_seed_is_within_the_range_ksampler_accepts() -> None:
    for _ in range(200):
        seed = _request(-1).resolved_seed()
        assert 0 <= seed <= MAX_SEED


def test_random_seeds_differ_between_chunks() -> None:
    request = _request(-1)
    seeds = {request.resolved_seed() for _ in range(50)}
    assert len(seeds) > 1, "every chunk of one request would otherwise be identical"


def test_default_request_seed_is_the_random_sentinel() -> None:
    request = VideoGenerationRequest(
        prompt="x", output_path=Path("x.mp4"), duration_seconds=1.0, width=64, height=64, fps=1,
    )
    assert request.seed == -1
    assert request.resolved_seed() >= 0
