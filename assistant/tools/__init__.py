"""
P.E.P.P.E.R. - Tool System

Created: August 9, 2026
Last Edited: August 9, 2026
Author: Max Maehara

Purpose:
    Provides controlled computer-action capabilities for P.E.P.P.E.R.

Phase:
    Phase 6 - Tool & Computer Control

Current Capabilities:
    - tool registry
    - permission / risk classification
    - workspace-scoped filesystem access
    - safe terminal execution
    - centralized tool execution
    - audit logging

Important:
    P.E.P.P.E.R.'s reasoning model does not directly execute arbitrary
    operating-system actions.

    All actions must pass through the tool registry, permission
    system, executor, and audit layer.
"""