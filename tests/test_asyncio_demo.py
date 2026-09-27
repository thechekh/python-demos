"""The three I/O schedules produce the shapes the article describes."""

import asyncio

import pytest

import asyncio_demo


@pytest.fixture(autouse=True)
def quick(monkeypatch):
    monkeypatch.setattr(asyncio_demo, "IO_SECONDS", 0.02)
    monkeypatch.setattr(asyncio_demo, "TASKS", 6)


def overlap(log):
    """How many downloads were in flight at the busiest moment."""
    return max(sum(1 for _, s, e in log if s <= t < e) for _, t, _ in log)


def test_one_after_another_never_overlaps():
    log = []
    asyncio.run(asyncio_demo.one_after_another(log))
    assert len(log) == 6 and overlap(log) == 1


def test_all_at_once_overlaps_completely():
    log = []
    asyncio.run(asyncio_demo.all_at_once(log))
    assert overlap(log) == 6


def test_bounded_never_exceeds_the_limit():
    log = []
    asyncio.run(asyncio_demo.at_most_three(log))
    assert len(log) == 6 and overlap(log) == asyncio_demo.LIMIT


def test_compute_is_deterministic():
    assert asyncio_demo.compute(1000) == asyncio_demo.compute(1000)
