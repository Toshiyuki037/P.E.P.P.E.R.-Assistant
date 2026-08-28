"""
P.E.P.P.E.R. Phase 16E Final Validation

Run from repository root:
    python .\validate_phase16e.py
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread

from assistant.events import EVENT_BUS
from assistant.events.definitions import (
    GOAL_COMPLETED,
    GOAL_CREATED,
    TASK_COMPLETED,
    TASK_CREATED,
    TASK_FAILED,
    TASK_STARTED,
)
from assistant.executive import TaskExecutive


def test_goal_task_lifecycle(path: Path):
    executive = TaskExecutive(path)

    goal = executive.create_goal(
        "Morning protocol",
        description="Build reusable morning briefing behavior.",
        priority=10,
    )

    task = executive.create_task(
        "Implement briefing composer",
        goal_id=goal.goal_id,
        priority=5,
    )

    assert executive.get_goal(goal.goal_id) is not None
    assert executive.get_task(task.task_id).status == "pending"

    running = executive.start_task(task.task_id)
    assert running.status == "running"
    assert running.started_at is not None

    completed = executive.complete_task(task.task_id)
    assert completed.status == "completed"
    assert completed.completed_at is not None

    completed_goal = executive.complete_goal(goal.goal_id)
    assert completed_goal.status == "completed"
    assert completed_goal.completed_at is not None

    print("PASS 16E lifecycle: goal/task create -> start -> complete")


def test_persistence_restart(path: Path):
    first = TaskExecutive(path)

    goal = first.create_goal(
        "Persistent goal",
        priority=3,
    )
    task = first.create_task(
        "Persistent task",
        goal_id=goal.goal_id,
        due_at="2030-01-01T09:00:00+00:00",
    )

    second = TaskExecutive(path)

    loaded_goal = second.get_goal(goal.goal_id)
    loaded_task = second.get_task(task.task_id)

    assert loaded_goal is not None
    assert loaded_goal.title == "Persistent goal"
    assert loaded_task is not None
    assert loaded_task.title == "Persistent task"
    assert loaded_task.goal_id == goal.goal_id

    print("PASS 16E persistence: state survives executive restart")


def test_filtering_priority(path: Path):
    executive = TaskExecutive(path)

    low = executive.create_task(
        "Low priority",
        priority=1,
    )
    high = executive.create_task(
        "High priority",
        priority=9,
    )
    executive.complete_task(low.task_id)

    pending = executive.list_tasks(
        status="pending",
    )

    assert [item.task_id for item in pending] == [
        high.task_id
    ]

    all_tasks = executive.list_tasks()
    assert all_tasks[0].task_id == high.task_id

    print("PASS 16E querying: status filtering + priority ordering")


def test_event_emission(path: Path):
    executive = TaskExecutive(path)
    seen = []

    topics = [
        GOAL_CREATED,
        GOAL_COMPLETED,
        TASK_CREATED,
        TASK_STARTED,
        TASK_COMPLETED,
        TASK_FAILED,
    ]

    tokens = [
        EVENT_BUS.subscribe(
            topic,
            lambda event, topic=topic: seen.append(
                (topic, event.payload)
            ),
        )
        for topic in topics
    ]

    try:
        goal = executive.create_goal("Event goal")
        task = executive.create_task(
            "Event task",
            goal_id=goal.goal_id,
        )
        executive.start_task(task.task_id)
        executive.fail_task(
            task.task_id,
            "controlled failure",
        )
        executive.start_task(task.task_id)
        executive.complete_task(task.task_id)
        executive.complete_goal(goal.goal_id)

        emitted_topics = [
            topic
            for topic, _ in seen
        ]

        for expected in topics:
            assert expected in emitted_topics, (
                f"Missing event: {expected}"
            )
    finally:
        for token in tokens:
            EVENT_BUS.unsubscribe(token)

    print("PASS 16E events: lifecycle changes emit Phase 16D events")


def test_goal_integrity(path: Path):
    executive = TaskExecutive(path)

    try:
        executive.create_task(
            "Orphan task",
            goal_id="goal_does_not_exist",
        )
    except KeyError:
        pass
    else:
        raise AssertionError(
            "Task attached to an unknown goal."
        )

    print("PASS 16E integrity: unknown goal references rejected")


def test_failure_record(path: Path):
    executive = TaskExecutive(path)

    task = executive.create_task(
        "Failure test",
    )

    failed = executive.fail_task(
        task.task_id,
        "controlled failure",
    )

    assert failed.status == "failed"
    assert failed.error == "controlled failure"

    completed = executive.complete_task(
        task.task_id,
    )

    assert completed.status == "completed"
    assert completed.error == ""

    print("PASS 16E failure state: failure retained and cleared on completion")


def test_thread_safety(path: Path):
    executive = TaskExecutive(path)

    def create(index):
        executive.create_task(
            f"Concurrent task {index}",
            priority=index,
        )

    threads = [
        Thread(
            target=create,
            args=(index,),
        )
        for index in range(20)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    tasks = executive.list_tasks()

    assert len(tasks) == 20
    assert len({
        task.task_id
        for task in tasks
    }) == 20

    # Reopen to ensure concurrent writes left a valid persistent file.
    reopened = TaskExecutive(path)
    assert len(reopened.list_tasks()) == 20

    print("PASS 16E thread safety: concurrent mutations persist correctly")


def run_isolated(test):
    with TemporaryDirectory() as temp:
        path = Path(temp) / "executive.json"
        test(path)


def main():
    print("P.E.P.P.E.R. Phase 16E Final Validation")
    print("--------------------------------------")

    for test in [
        test_goal_task_lifecycle,
        test_persistence_restart,
        test_filtering_priority,
        test_event_emission,
        test_goal_integrity,
        test_failure_record,
        test_thread_safety,
    ]:
        run_isolated(test)

    print()
    print("PHASE 16E FINAL VALIDATION PASSED")


if __name__ == "__main__":
    main()
