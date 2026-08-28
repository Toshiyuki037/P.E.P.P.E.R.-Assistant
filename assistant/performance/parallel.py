"""
P.E.P.P.E.R. - Parallel Execution Primitive

Phase 16C.1

Purpose:
    Run independent, read-only work concurrently without changing the
    integration provider, routing, permission, or verification architecture.

Design:
    - bounded ThreadPoolExecutor
    - per-job timing
    - exception isolation
    - deterministic result ordering
    - no implicit retries
    - no cancellation assumptions
"""

from __future__ import annotations

from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from dataclasses import (
    asdict,
    dataclass,
)
from time import perf_counter
from typing import (
    Any,
    Callable,
)


@dataclass(frozen=True)
class ParallelJob:
    name: str
    function: Callable[..., Any]
    args: tuple = ()
    kwargs: dict | None = None


@dataclass
class ParallelJobResult:
    name: str
    success: bool
    value: Any = None
    error: str = ""
    elapsed_seconds: float = 0.0

    def to_dict(self):
        return asdict(self)


def _run_job(job: ParallelJob):
    started = perf_counter()

    try:
        value = job.function(
            *job.args,
            **(job.kwargs or {}),
        )

        return ParallelJobResult(
            name=job.name,
            success=True,
            value=value,
            elapsed_seconds=(
                perf_counter()
                - started
            ),
        )

    except Exception as error:
        return ParallelJobResult(
            name=job.name,
            success=False,
            error=str(error),
            elapsed_seconds=(
                perf_counter()
                - started
            ),
        )


def execute_parallel(
    jobs: list[ParallelJob],
    max_workers: int = 4,
):
    """
    Execute independent jobs concurrently.

    Results are returned in the same order as the input jobs even though
    execution completes concurrently.

    Exceptions are captured per job so one failed source does not discard
    successful sibling results.
    """

    if not jobs:
        return []

    worker_count = max(
        1,
        min(
            int(max_workers),
            len(jobs),
        ),
    )

    started = perf_counter()

    indexed_results = {}

    with ThreadPoolExecutor(
        max_workers=worker_count,
        thread_name_prefix="pepper-prefetch",
    ) as executor:

        future_to_index = {
            executor.submit(
                _run_job,
                job,
            ): index
            for index, job in enumerate(jobs)
        }

        for future in as_completed(
            future_to_index
        ):
            index = future_to_index[
                future
            ]

            try:
                indexed_results[index] = (
                    future.result()
                )

            except Exception as error:
                # _run_job already isolates normal job exceptions. This is a
                # defensive boundary for executor/future failures themselves.
                indexed_results[index] = (
                    ParallelJobResult(
                        name=jobs[index].name,
                        success=False,
                        error=str(error),
                    )
                )

    elapsed = (
        perf_counter()
        - started
    )

    results = [
        indexed_results[index]
        for index in range(
            len(jobs)
        )
    ]

    print()
    print(
        "[Parallel Execution Timing]"
    )
    print(
        f"jobs: {len(jobs)}"
    )
    print(
        f"workers: {worker_count}"
    )
    print(
        f"parallel_total: {elapsed:.3f}s"
    )

    for result in results:
        print(
            (
                f"{result.name}: "
                f"{result.elapsed_seconds:.3f}s "
                f"success={result.success}"
            )
        )

    return results


if __name__ == "__main__":
    from time import sleep

    def diagnostic_job(
        label,
        delay,
        fail=False,
    ):
        sleep(delay)

        if fail:
            raise RuntimeError(
                f"{label} diagnostic failure"
            )

        return label

    diagnostic_jobs = [
        ParallelJob(
            name="weather",
            function=diagnostic_job,
            args=("weather", 0.35),
        ),
        ParallelJob(
            name="email",
            function=diagnostic_job,
            args=("email", 0.35),
        ),
        ParallelJob(
            name="calendar",
            function=diagnostic_job,
            args=("calendar", 0.35),
        ),
        ParallelJob(
            name="market",
            function=diagnostic_job,
            args=("market", 0.35),
        ),
    ]

    diagnostic_started = (
        perf_counter()
    )

    diagnostic_results = (
        execute_parallel(
            diagnostic_jobs,
            max_workers=4,
        )
    )

    diagnostic_elapsed = (
        perf_counter()
        - diagnostic_started
    )

    print()
    print(
        "P.E.P.P.E.R. Phase 16C.1 Diagnostic"
    )
    print(
        "---------------------------------"
    )

    for result in diagnostic_results:
        print(
            result.to_dict()
        )

    print(
        (
            "Wall time: "
            f"{diagnostic_elapsed:.3f}s"
        )
    )
