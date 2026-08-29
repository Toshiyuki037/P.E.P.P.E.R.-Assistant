"""
P.E.P.P.E.R. - Workflow Package

Phase 11

Important:
This package intentionally performs no eager imports.

Background services such as the scheduler must be able to start
without loading:
    - P.E.P.P.E.R. reasoning
    - semantic memory
    - sentence transformers
    - speech systems
    - browser systems

Import workflow functionality directly from the required module.

Examples:

    from assistant.capabilities.workflows.protocols import run_protocol

    from assistant.capabilities.workflows.controller import run_workflow

    from assistant.capabilities.workflows.schedules import create_schedule
"""