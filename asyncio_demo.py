"""asyncio from the ground up.

Article: https://chekh.dev/writing/asyncio-from-the-ground-up/
Run:     uv run python asyncio_demo.py                 (about thirty seconds)
         uv run python asyncio_demo.py --charts-only   (redraw from results/)

Ten pretend downloads run one after another, then all at once, then at most three at
a time. Then ten pieces of real computation the same ways, plus a thread pool and a
process pool. A heartbeat task ticks throughout, and shows when the event loop is
blocked.
"""

import asyncio
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import matplotlib.pyplot as plt

from _common import ACCENT, INK, INK_2, MUTED, save

SLUG = "asyncio-from-the-ground-up"
TASKS = 10
IO_SECONDS = 0.5  # how long each pretend download waits
CPU_LOOPS = 6_000_000  # about half a second of arithmetic per task
LIMIT = 3  # for the bounded version


async def download(i: int, log: list) -> None:
    """A pretend download: it waits, and while it waits the event loop is free."""
    started = time.perf_counter()
    await asyncio.sleep(IO_SECONDS)
    log.append((i, started, time.perf_counter()))


def compute(n: int = CPU_LOOPS) -> int:
    """Real work: a loop the processor has to run. Nothing here waits."""
    total = 0
    for k in range(n):
        total += k * k % 7
    return total


async def one_after_another(log: list) -> None:
    for i in range(TASKS):
        await download(i, log)


async def all_at_once(log: list) -> None:
    await asyncio.gather(*(download(i, log) for i in range(TASKS)))


async def at_most_three(log: list) -> None:
    limit = asyncio.Semaphore(LIMIT)

    async def limited(i: int) -> None:
        async with limit:  # waits here when three are already running
            await download(i, log)

    await asyncio.gather(*(limited(i) for i in range(TASKS)))


async def cpu_in_coroutines() -> None:
    """Looks concurrent. Is not: compute() never awaits, so nothing else can run."""

    async def work() -> int:
        return compute()

    await asyncio.gather(*(work() for _ in range(TASKS)))


async def cpu_in_threads() -> None:
    """The loop stays free, but the GIL lets only one thread compute at a time."""
    await asyncio.gather(*(asyncio.to_thread(compute) for _ in range(TASKS)))


async def cpu_in_processes(pool: ProcessPoolExecutor) -> None:
    """Separate processes, separate GILs: the only one that runs in parallel."""
    loop = asyncio.get_running_loop()
    jobs = (loop.run_in_executor(pool, compute) for _ in range(TASKS))
    await asyncio.gather(*jobs)


async def cpu_in_a_fresh_process_pool() -> None:
    """Starting the workers is part of the bill — on Windows, a second or two of it."""
    with ProcessPoolExecutor() as pool:
        await cpu_in_processes(pool)


async def heartbeat(ticks: list, stop: asyncio.Event) -> None:
    """Ticks every 50 ms — if the loop lets it."""
    while not stop.is_set():
        ticks.append(time.perf_counter())
        await asyncio.sleep(0.05)


async def timed(coro_fn, *args) -> tuple[float, list]:
    """Run a coroutine with a heartbeat alongside; return its duration and the ticks."""
    ticks, stop = [], asyncio.Event()
    beat = asyncio.create_task(heartbeat(ticks, stop))
    await asyncio.sleep(0.12)  # let the heartbeat tick twice before the work starts
    start = time.perf_counter()
    await coro_fn(*args)
    seconds = time.perf_counter() - start
    stop.set()
    await beat
    # The end of the work counts as a tick too, or a stall that lasts to the end is invisible.
    return seconds, [t - start for t in ticks] + [seconds]


async def main() -> dict:
    results: dict = {"tasks": TASKS, "io_seconds": IO_SECONDS, "limit": LIMIT, "io": {}, "cpu": {}}
    one_compute = time.perf_counter()
    compute()
    results["one_compute_seconds"] = time.perf_counter() - one_compute
    print(f"one compute() call: {results['one_compute_seconds']:.2f} s")

    for name, fn in [("one after another", one_after_another), ("all at once", all_at_once), (f"at most {LIMIT} at a time", at_most_three)]:
        log: list = []
        start = time.perf_counter()
        seconds, ticks = await timed(fn, log)
        results["io"][name] = {"seconds": seconds, "spans": [(i, s - start, e - start) for i, s, e in log], "max_gap": max_gap(ticks)}
        print(f"I/O  {name:24s} {seconds:5.2f} s   longest pause in the heartbeat {results['io'][name]['max_gap'] * 1000:4.0f} ms")

    # Workers start lazily, one per submitted job, in the caller's thread: a full batch
    # now means the last row measures the work and not the start-up.
    warm_pool = ProcessPoolExecutor()
    list(warm_pool.map(compute, [1] * TASKS))
    cpu_runs = [
        ("in coroutines", cpu_in_coroutines, ()),
        ("in a thread pool", cpu_in_threads, ()),
        ("in a fresh process pool", cpu_in_a_fresh_process_pool, ()),
        ("in a running process pool", cpu_in_processes, (warm_pool,)),
    ]
    for name, fn, args in cpu_runs:
        seconds, ticks = await timed(fn, *args)
        results["cpu"][name] = {"seconds": seconds, "ticks": ticks, "max_gap": max_gap(ticks)}
        print(f"CPU  {name:26s} {seconds:5.2f} s   longest pause in the heartbeat {results['cpu'][name]['max_gap'] * 1000:4.0f} ms")
    warm_pool.shutdown()
    return results


def max_gap(ticks: list) -> float:
    return max((b - a for a, b in zip(ticks, ticks[1:])), default=0.0)


def draw_timeline(results: dict) -> None:
    names = list(results["io"])
    fig, axes = plt.subplots(len(names), 1, figsize=(7.2, 4.6), sharex=True)
    for ax, name in zip(axes, names):
        run = results["io"][name]
        for i, start, end in run["spans"]:
            ax.barh(i, end - start, left=start, height=0.7, color=ACCENT if name == "all at once" else INK_2)
        ax.set_ylim(-0.7, results["tasks"] - 0.3)
        ax.set_yticks([0, results["tasks"] - 1], ["task 0", f"task {results['tasks'] - 1}"], fontsize=8.5)
        ax.invert_yaxis()
        ax.grid(axis="y", visible=False)
        ax.set_title(f"{name}: {run['seconds']:.1f} s", fontsize=10, loc="left")
    axes[-1].set_xlabel("seconds")
    fig.tight_layout()
    save(fig, SLUG, "timeline")


def draw_heartbeat(results: dict) -> None:
    names = list(results["cpu"])
    fig, ax = plt.subplots(figsize=(7.4, 3.3))
    for row, name in enumerate(names):
        run = results["cpu"][name]
        ticks = [t for t in run["ticks"] if 0 <= t < run["seconds"]]  # the heartbeats during the work
        ax.eventplot(ticks, lineoffsets=row, linelengths=0.6, colors=[ACCENT if run["max_gap"] < 0.5 else INK_2], linewidths=1)
        ax.plot([0, run["seconds"]], [row + 0.42, row + 0.42], color=MUTED, linewidth=1)
        ax.text(-0.1, row, f"{name}\n{run['seconds']:.1f} s, longest pause {run['max_gap'] * 1000:.0f} ms", ha="right", va="center", fontsize=8.5, color=INK, linespacing=1.3)
    ax.set_yticks([])
    ax.set_ylim(-0.6, len(names) - 0.4)
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, max(r["seconds"] for r in results["cpu"].values()) * 1.04)
    ax.set_xlabel("seconds — each tick is a heartbeat the event loop managed to run; the bar is the work")
    ax.set_title("Ten computations, and whether the loop stayed responsive", fontsize=10.5)
    fig.subplots_adjust(left=0.36)
    save(fig, SLUG, "heartbeat")


if __name__ == "__main__":
    path = Path(__file__).parent / "results" / f"{SLUG}.json"
    if "--charts-only" in sys.argv:
        results = json.loads(path.read_text())
    else:
        results = asyncio.run(main())
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(results))
        print(f"  wrote {path.name}")
    draw_timeline(results)
    draw_heartbeat(results)
