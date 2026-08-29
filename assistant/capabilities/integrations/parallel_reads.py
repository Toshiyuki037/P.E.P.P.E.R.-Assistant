"""
P.E.P.P.E.R. - Parallel Integration Reads

Phase 16C.2

Purpose:
    Execute independent, low-risk integration reads concurrently while
    preserving the existing Phase 9 aggregator, routing, permissions, and
    provider execution paths.

Safety:
    - only capabilities that do NOT require approval may run here
    - approved is always False
    - each request still goes through execute_aggregate()
    - failures are isolated per capability
    - no write action is permitted through this batch path
"""

from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
    field,
)
from time import perf_counter
from typing import Any

from assistant.observability.performance.parallel import (
    ParallelJob,
    execute_parallel,
)

from .aggregator import (
    aggregate_result_to_dict,
    capability_requires_approval,
    execute_aggregate,
)


@dataclass(frozen=True)
class IntegrationReadRequest:
    name: str
    capability: str
    arguments: dict = field(
        default_factory=dict
    )
    routing_mode: str = "all_available"
    provider: str | None = None
    account_id: str | None = None


@dataclass
class IntegrationReadResult:
    name: str
    capability: str
    success: bool
    aggregate: Any = None
    error: str = ""
    elapsed_seconds: float = 0.0

    def to_dict(self):
        payload = asdict(self)

        aggregate = self.aggregate

        if aggregate is not None:
            try:
                payload[
                    "aggregate"
                ] = aggregate_result_to_dict(
                    aggregate
                )
            except Exception:
                payload[
                    "aggregate"
                ] = str(
                    aggregate
                )

        return payload


def _execute_read_request(
    request: IntegrationReadRequest,
):
    """
    Execute exactly one request through the existing aggregator.

    This wrapper deliberately does not bypass routing, permissions, provider
    adapters, account selection, or aggregate evidence handling.
    """

    if capability_requires_approval(
        request.capability
    ):
        raise PermissionError(
            (
                "Parallel integration reads may only execute "
                "non-approval capabilities. "
                f"Blocked: {request.capability}"
            )
        )

    return execute_aggregate(
        capability=request.capability,
        arguments=dict(
            request.arguments
        ),
        routing_mode=request.routing_mode,
        provider=request.provider,
        account_id=request.account_id,
        approved=False,
    )


def execute_parallel_integration_reads(
    requests: list[
        IntegrationReadRequest
    ],
    max_workers: int = 4,
):
    """
    Execute independent low-risk integration reads concurrently.

    The returned list follows request order, regardless of completion order.
    A failed capability does not discard successful sibling results.
    """

    if not requests:
        return []

    # Fail closed before launching any work if a write/approval capability was
    # accidentally included in the batch.
    for request in requests:
        if capability_requires_approval(
            request.capability
        ):
            raise PermissionError(
                (
                    "Parallel integration batch rejected because "
                    f"{request.capability} requires approval."
                )
            )

    jobs = [
        ParallelJob(
            name=request.name,
            function=_execute_read_request,
            args=(request,),
        )
        for request in requests
    ]

    batch_started = (
        perf_counter()
    )

    parallel_results = (
        execute_parallel(
            jobs,
            max_workers=max_workers,
        )
    )

    batch_elapsed = (
        perf_counter()
        - batch_started
    )

    results = []

    for request, parallel_result in zip(
        requests,
        parallel_results,
    ):
        aggregate = (
            parallel_result.value
            if parallel_result.success
            else None
        )

        aggregate_success = bool(
            aggregate
            and getattr(
                aggregate,
                "success",
                False,
            )
        )

        results.append(
            IntegrationReadResult(
                name=request.name,
                capability=request.capability,
                success=(
                    parallel_result.success
                    and aggregate_success
                ),
                aggregate=aggregate,
                error=(
                    parallel_result.error
                    if not parallel_result.success
                    else (
                        ""
                        if aggregate_success
                        else "Integration aggregate returned no successful source."
                    )
                ),
                elapsed_seconds=(
                    parallel_result.elapsed_seconds
                ),
            )
        )

    print()
    print(
        "[Parallel Integration Read Timing]"
    )
    print(
        f"requests: {len(requests)}"
    )
    print(
        f"batch_total: {batch_elapsed:.3f}s"
    )

    for result in results:
        print(
            (
                f"{result.name}: "
                f"{result.elapsed_seconds:.3f}s "
                f"success={result.success} "
                f"capability={result.capability}"
            )
        )

    return results


if __name__ == "__main__":
    print(
        "P.E.P.P.E.R. Phase 16C.2"
    )
    print(
        "------------------------"
    )
    print(
        "Parallel integration read layer loaded."
    )
    print(
        "Use execute_parallel_integration_reads() with real "
        "low-risk IntegrationReadRequest objects."
    )
