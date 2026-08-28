"""
P.E.P.P.E.R. Phase 16F Final Validation

Run from repository root:
    python .\validate_phase16f.py
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Lock
from time import perf_counter, sleep

from assistant.background import (
    BackgroundHandlerRegistry,
    BackgroundWorker,
)
from assistant.events import EVENT_BUS
from assistant.events.definitions import (
    BACKGROUND_JOB_FINISHED,
    BACKGROUND_JOB_STARTED,
)
from assistant.executive import TaskExecutive


def make_stack(path: Path, max_workers: int = 4):
    executive = TaskExecutive(path)
    registry = BackgroundHandlerRegistry()
    worker = BackgroundWorker(
        executive=executive,
        registry=registry,
        max_workers=max_workers,
    )
    return executive, registry, worker


def create_background_task(
    executive,
    title,
    handler,
    *,
    priority=0,
):
    return executive.create_task(
        title,
        priority=priority,
        metadata={
            "background_handler": handler,
        },
    )


def test_basic_execution(path: Path):
    executive, registry, worker = make_stack(path)

    registry.register(
        "echo",
        lambda task: {
            "task": task.title,
            "ok": True,
        },
    )

    task = create_background_task(
        executive,
        "Echo task",
        "echo",
    )

    worker.start()
    try:
        result = worker.submit(task.task_id).result(timeout=3)
    finally:
        worker.stop()

    assert result.success is True
    assert result.value["ok"] is True
    assert executive.get_task(task.task_id).status == "completed"

    print("PASS 16F basic background execution")


def test_bounded_parallelism(path: Path):
    executive, registry, worker = make_stack(
        path,
        max_workers=4,
    )

    def delayed(task):
        sleep(0.30)
        return task.title

    registry.register("delayed", delayed)

    tasks = [
        create_background_task(
            executive,
            f"Parallel {index}",
            "delayed",
        )
        for index in range(4)
    ]

    worker.start()
    started = perf_counter()
    try:
        futures = [
            worker.submit(task.task_id)
            for task in tasks
        ]
        results = [
            future.result(timeout=3)
            for future in futures
        ]
    finally:
        worker.stop()

    elapsed = perf_counter() - started

    assert all(result.success for result in results)
    assert elapsed < 0.80, (
        f"Expected parallel execution; wall={elapsed:.3f}s"
    )

    print(
        f"PASS 16F bounded parallelism: four 0.30s tasks in {elapsed:.3f}s"
    )


def test_failure_isolation(path: Path):
    executive, registry, worker = make_stack(path)

    def good(task):
        sleep(0.10)
        return "ok"

    def bad(task):
        sleep(0.10)
        raise RuntimeError("controlled background failure")

    registry.register("good", good)
    registry.register("bad", bad)

    good_task = create_background_task(
        executive,
        "Good task",
        "good",
    )
    bad_task = create_background_task(
        executive,
        "Bad task",
        "bad",
    )

    worker.start()
    try:
        good_future = worker.submit(good_task.task_id)
        bad_future = worker.submit(bad_task.task_id)

        good_result = good_future.result(timeout=3)
        bad_result = bad_future.result(timeout=3)
    finally:
        worker.stop()

    assert good_result.success is True
    assert bad_result.success is False
    assert executive.get_task(good_task.task_id).status == "completed"

    failed = executive.get_task(bad_task.task_id)
    assert failed.status == "failed"
    assert "controlled background failure" in failed.error

    print("PASS 16F failure isolation + persistent failed state")


def test_duplicate_protection(path: Path):
    executive, registry, worker = make_stack(
        path,
        max_workers=2,
    )

    gate = Event()

    def waiting(task):
        gate.wait(timeout=2)
        return "released"

    registry.register("waiting", waiting)

    task = create_background_task(
        executive,
        "Duplicate protection",
        "waiting",
    )

    worker.start()
    try:
        first = worker.submit(task.task_id)

        try:
            worker.submit(task.task_id)
        except RuntimeError as error:
            assert "already running" in str(error)
        else:
            raise AssertionError(
                "Duplicate in-flight task was accepted."
            )

        gate.set()
        assert first.result(timeout=3).success is True
    finally:
        gate.set()
        worker.stop()

    print("PASS 16F duplicate in-flight protection")


def test_allowlist_boundary(path: Path):
    executive, registry, worker = make_stack(path)

    missing = create_background_task(
        executive,
        "Missing handler",
        "not_registered",
    )

    no_handler = executive.create_task(
        "No handler metadata"
    )

    worker.start()
    try:
        for task in [missing, no_handler]:
            try:
                worker.submit(task.task_id)
            except (KeyError, ValueError):
                pass
            else:
                raise AssertionError(
                    "Unauthorized background task was accepted."
                )
    finally:
        worker.stop()

    assert executive.get_task(missing.task_id).status == "pending"
    assert executive.get_task(no_handler.task_id).status == "pending"

    print("PASS 16F explicit handler allow-list boundary")


def test_events(path: Path):
    executive, registry, worker = make_stack(path)
    seen = []

    registry.register(
        "event-test",
        lambda task: "done",
    )

    task = create_background_task(
        executive,
        "Event task",
        "event-test",
    )

    tokens = [
        EVENT_BUS.subscribe(
            BACKGROUND_JOB_STARTED,
            lambda event: seen.append(event.topic),
        ),
        EVENT_BUS.subscribe(
            BACKGROUND_JOB_FINISHED,
            lambda event: seen.append(event.topic),
        ),
    ]

    worker.start()
    try:
        result = worker.submit(task.task_id).result(timeout=3)
    finally:
        worker.stop()
        for token in tokens:
            EVENT_BUS.unsubscribe(token)

    assert result.success is True
    assert BACKGROUND_JOB_STARTED in seen
    assert BACKGROUND_JOB_FINISHED in seen

    print("PASS 16F Phase 16D event integration")


def test_graceful_shutdown(path: Path):
    executive, registry, worker = make_stack(
        path,
        max_workers=2,
    )

    registry.register(
        "short",
        lambda task: (
            sleep(0.15),
            "done",
        )[1],
    )

    tasks = [
        create_background_task(
            executive,
            f"Shutdown {index}",
            "short",
        )
        for index in range(2)
    ]

    worker.start()
    futures = [
        worker.submit(task.task_id)
        for task in tasks
    ]

    worker.stop(wait=True)

    assert all(
        future.done()
        for future in futures
    )
    assert all(
        executive.get_task(task.task_id).status == "completed"
        for task in tasks
    )

    print("PASS 16F graceful shutdown waits for running work")


def run_isolated(test):
    with TemporaryDirectory() as temp:
        test(Path(temp) / "executive.json")


def main():
    print("P.E.P.P.E.R. Phase 16F Final Validation")
    print("--------------------------------------")

    for test in [
        test_basic_execution,
        test_bounded_parallelism,
        test_failure_isolation,
        test_duplicate_protection,
        test_allowlist_boundary,
        test_events,
        test_graceful_shutdown,
    ]:
        run_isolated(test)

    print()
    print("PHASE 16F FINAL VALIDATION PASSED")


if __name__ == "__main__":
    main()
