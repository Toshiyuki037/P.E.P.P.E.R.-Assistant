"""
P.E.P.P.E.R. - Parallel Integration Prefetch

Phase 16C.3

Purpose:
    Execute independent low-risk integration reads concurrently and publish
    each successful result into the Phase 16B world-state RAM.

Safety:
    - delegates execution to parallel_reads
    - parallel_reads delegates each request to the existing aggregator
    - no write/approval capability is allowed
    - failed reads never overwrite world state
    - each successful source is published independently
"""

from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
)
from time import perf_counter

from .aggregator import (
    aggregate_result_to_dict,
)
from .parallel_reads import (
    IntegrationReadRequest,
    IntegrationReadResult,
    execute_parallel_integration_reads,
)

from assistant.core.world_state.integration_adapter import (
    publish_integration_execution,
)


@dataclass
class IntegrationPrefetchResult:
    name: str
    capability: str
    success: bool
    published: bool
    world_state_key: str = ""
    error: str = ""
    elapsed_seconds: float = 0.0

    def to_dict(self):
        return asdict(self)


def _execution_payload(
    request: IntegrationReadRequest,
    result: IntegrationReadResult,
):
    """
    Adapt the existing AggregatedIntegrationResult into the execution shape
    already understood by the Phase 16B integration world-state adapter.
    """

    aggregate = result.aggregate

    if aggregate is None:
        return None

    aggregate_dict = (
        aggregate_result_to_dict(
            aggregate
        )
    )

    return {
        "success": bool(
            aggregate_dict.get(
                "success"
            )
        ),
        "capability": request.capability,
        "provider": request.provider or "",
        "account_id": request.account_id or "",
        "routing_mode": request.routing_mode,
        "result": aggregate_dict,
    }


def prefetch_integrations_to_world_state(
    requests: list[
        IntegrationReadRequest
    ],
    max_workers: int = 4,
):
    """
    Run independent integration reads in parallel and publish successful
    results to world state.

    Partial failure is intentional: one failed source does not erase or block
    successful sibling state.
    """

    started = perf_counter()

    read_results = (
        execute_parallel_integration_reads(
            requests,
            max_workers=max_workers,
        )
    )

    results = []

    for request, read_result in zip(
        requests,
        read_results,
    ):
        published_record = None
        error = read_result.error

        if read_result.success:
            execution = _execution_payload(
                request,
                read_result,
            )

            if execution is not None:
                try:
                    published_record = (
                        publish_integration_execution(
                            execution,
                            capability=request.capability,
                            provider=request.provider,
                            account_id=request.account_id,
                            routing_mode=request.routing_mode,
                        )
                    )
                except Exception as publish_error:
                    error = str(
                        publish_error
                    )

        results.append(
            IntegrationPrefetchResult(
                name=request.name,
                capability=request.capability,
                success=read_result.success,
                published=(
                    published_record
                    is not None
                ),
                world_state_key=(
                    published_record.key
                    if published_record
                    is not None
                    else ""
                ),
                error=error,
                elapsed_seconds=(
                    read_result.elapsed_seconds
                ),
            )
        )

    elapsed = (
        perf_counter()
        - started
    )

    print()
    print(
        "[Integration Prefetch Timing]"
    )
    print(
        f"requests: {len(requests)}"
    )
    print(
        f"prefetch_total: {elapsed:.3f}s"
    )

    for result in results:
        print(
            (
                f"{result.name}: "
                f"success={result.success} "
                f"published={result.published} "
                f"key={result.world_state_key or '-'}"
            )
        )

    return results


if __name__ == "__main__":
    print(
        "P.E.P.P.E.R. Phase 16C.3"
    )
    print(
        "------------------------"
    )
    print(
        "Parallel integration prefetch -> world-state layer loaded."
    )
    print(
        "Successful reads publish independently into Phase 16B RAM."
    )
