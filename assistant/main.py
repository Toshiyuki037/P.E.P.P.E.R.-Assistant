"""
P.E.P.P.E.R. - Main Application Controller

Created: August 7, 2026
Last Edited: August 8, 2026
Author: Max Maehara

Purpose:
    Main runtime for Enhanced Virtual Intelligence Engine.

How It Works:
    Supports voice and terminal input.

    Incoming messages may:
        - create long-term memories
        - merge duplicate memories
        - supersede outdated memories
        - update existing memories
        - forget/archive one or multiple memories
        - use live computer context
        - trigger normal reasoning

    The complete response is displayed in the terminal while a cleaned,
    shorter version is sent to P.E.P.P.E.R.'s voice model.

Most Recent Change:
    Added Phase 6 controlled computer-tool requests and explicit
    approval continuation while preserving memory, voice, and normal reasoning.
"""

from .brain import (
    chat,
    handle_pending_tool_approval,
    handle_tool_request,
)
from .listen import listen
from .speech_formatter import prepare_spoken_text

from .speak import (
    play_audio,
    speak,
    speak_streaming_response,
    pause_audio,
    resume_audio,
    stop_audio,
    synthesize_audio,
)

from .voice.authoritative_reasoning import (
    stream_authoritative_chat,
)

from .voice.authoritative_speech import (
    AuthoritativeSpeechPipeline,
)

from .voice.response_length import (
    apply_response_length_policy,
)

from .voice.presentation import (
    build_contextual_expansion_prompt,
    prepare_voice_presentation,
)

from .observability.performance import (
    classify_request_cost,
    performance_request_context,
    start_background_prewarm,
)

from .observability.performance.conversation_fastpath import (
    handle_fast_conversation,
)

from .observability.performance.context_budget import (
    context_budget_for_profile,
)

from .observability.performance.project_bridge import (
    augment_with_project_evidence,
)

from .voice.tts_prewarm import (
    start_tts_prewarm,
)

from .observability.performance.model_router import (
    should_use_fast_voice_reasoning,
)

from .voice.fast_reasoning import (
    stream_fast_authoritative_chat,
)

from .memory.database import (
    archive_memories,
    init_memory,
    save_conversation,
    save_memory,
    update_memory,
)

from .memory.embeddings import (
    create_memory_embedding,
    sync_memory_embeddings,
)

from .memory.manager import (
    RELATION_CONFIDENCE,
    analyze_memory,
    resolve_new_memory,
    select_forget_targets,
    select_update_targets,
    should_auto_delete,
    should_auto_store,
    should_auto_update,
)

from .memory.retriever import (
    retrieve_matching_memories,
    retrieve_memories,
)

from .agent.integration import (
    handle_agent_message,
)

from .intelligence.preferences import (
    handle_preference_command,
)

from .workflows.integration import (
    handle_pending_workflow_approval,
    handle_workflow_message,
)

from .coding.integration import (
    handle_coding_message,
)

from .computer.integration import (
    handle_computer_message,
)

from .observability.telemetry import (
    clear_request,
    finish_request,
    mark,
    persist_telemetry,
    print_latency_report,
    span,
    start_request,
)

from .voice.session import (
    run_voice_session,
)

from .voice.authentication import (
    NOT_RECOGNIZED_LINE,
    authenticate_last_wake_utterance,
    authenticated_wake_line,
)

from .voice.acknowledgements import (
    choose_acknowledgement,
    play_acknowledgement,
    suppress_next_acknowledgement,
)

# P.E.P.P.E.R.: old prerecorded acknowledgements disabled.
VOICE_ACKNOWLEDGEMENTS_ENABLED = False

from .system.integration import (
    handle_system_message,
)

from .briefings.morning import (
    run_good_morning_protocol,
)

from .briefings.scheduler import (
    GoodMorningScheduler,
    protocol_status,
)

# ---------------------------------------------------------------------------
# Speak Model Response
# ---------------------------------------------------------------------------

def speak_response(
    user_text: str,
    response: str,
):
    if not response:
        return

    presentation = (
        prepare_voice_presentation(
            user_text,
            response,
        )
    )

    spoken_response = (
        presentation.text
        .strip()
    )

    if not spoken_response:
        return

    speak_streaming_response(
        spoken_response,
        sentences_per_chunk=
            2,
        max_chunk_characters=
            340,
    )

# ---------------------------------------------------------------------------
# Store Memory
# ---------------------------------------------------------------------------

def store_memory(
    content,
    category,
    importance,
    permanence,
    confidence,
    source,
):
    """
    Creates a local semantic embedding and stores a new memory.
    """

    embedding = (
        create_memory_embedding(
            content
        )
    )

    memory_id = save_memory(
        content=content,
        category=category,
        importance=importance,
        permanence=permanence,
        confidence=confidence,
        source=source,
        embedding=embedding,
    )

    return memory_id


# ---------------------------------------------------------------------------
# Resolve New Memory
# ---------------------------------------------------------------------------

def store_with_resolution(
    content,
    category,
    importance,
    permanence,
    confidence,
    source,
):
    """
    Determines whether incoming information is:

        - new
        - duplicate
        - superseding old information
        - contradictory
        - merely related
    """

    candidates = retrieve_memories(
        query=content,
        limit=5,
    )

    resolution = resolve_new_memory(
        new_content=content,
        candidates=candidates,
    )


    # -----------------------------------------------------------------------
    # Duplicate
    # -----------------------------------------------------------------------

    if (
        resolution.relation
        == "duplicate"

        and resolution.matching_memory_id
        is not None

        and resolution.confidence
        >= RELATION_CONFIDENCE
    ):

        existing = next(
            (
                memory
                for memory in candidates

                if (
                    memory["id"]
                    == resolution.matching_memory_id
                )
            ),
            None,
        )

        if existing is not None:

            improved_importance = max(
                existing["importance"],
                importance,
            )

            improved_permanence = max(
                existing["permanence"],
                permanence,
            )

            improved_confidence = max(
                existing["confidence"],
                confidence,
            )

            embedding = (
                create_memory_embedding(
                    content
                )
            )

            update_memory(
                memory_id=existing["id"],
                content=content,
                category=category,
                importance=improved_importance,
                permanence=improved_permanence,
                confidence=improved_confidence,
                source=source,
                embedding=embedding,
            )

            print(
                "\n[Memory Manager: "
                "DUPLICATE MERGED]"
            )

            print(
                f"Memory ID: "
                f"{existing['id']}"
            )

            print(
                f"Memory: {content}"
            )

            return existing["id"]


    # -----------------------------------------------------------------------
    # Supersession / Contradiction
    # -----------------------------------------------------------------------

    if (
        resolution.relation
        in {
            "supersedes",
            "contradicts",
        }

        and resolution.matching_memory_id
        is not None

        and resolution.confidence
        >= RELATION_CONFIDENCE
    ):

        new_id = store_memory(
            content=content,
            category=category,
            importance=importance,
            permanence=permanence,
            confidence=confidence,
            source=source,
        )

        archived = archive_memories(
            [
                resolution.matching_memory_id
            ],
            reason=resolution.relation,
            superseded_by=new_id,
        )

        print(
            "\n[Memory Manager: SUPERSEDE]"
        )

        print(
            f"Archived IDs: "
            f"{archived}"
        )

        print(
            f"New ID: {new_id}"
        )

        print(
            f"Memory: {content}"
        )

        return new_id


    # -----------------------------------------------------------------------
    # New Distinct Memory
    # -----------------------------------------------------------------------

    memory_id = store_memory(
        content=content,
        category=category,
        importance=importance,
        permanence=permanence,
        confidence=confidence,
        source=source,
    )

    print(
        "\n[Memory Manager: STORE]"
    )

    print(
        f"ID: {memory_id}"
    )

    print(
        f"Memory: {content}"
    )

    return memory_id


# ---------------------------------------------------------------------------
# Explicit Remember Command
# ---------------------------------------------------------------------------

def handle_manual_memory(
    user_text,
):
    prefix = "remember that "

    if not user_text.lower().startswith(
        prefix
    ):
        return False

    content = user_text[
        len(prefix):
    ].strip()

    if not content:

        response = (
            "Tell me what you'd like "
            "me to remember."
        )

    else:

        store_with_resolution(
            content=content,
            category="general",
            importance=100,
            permanence=100,
            confidence=100,
            source="manual",
        )

        response = (
            "I'll remember that."
        )

    print(
        f"\nP.E.P.P.E.R.: "
        f"{response}\n"
    )

    speak(
        response
    )

    return True


# ---------------------------------------------------------------------------
# Intelligent Memory Processing
# ---------------------------------------------------------------------------

def process_intelligent_memory(
    user_text,
):
    try:

        analysis = analyze_memory(
            user_text
        )


        # -------------------------------------------------------------------
        # NONE
        # -------------------------------------------------------------------

        if analysis.action == "none":
            return


        # -------------------------------------------------------------------
        # STORE
        # -------------------------------------------------------------------

        if should_auto_store(
            analysis
        ):

            store_with_resolution(
                content=analysis.content,
                category=analysis.category,
                importance=analysis.importance,
                permanence=analysis.permanence,
                confidence=analysis.confidence,
                source="automatic",
            )

            return


        # -------------------------------------------------------------------
        # UPDATE
        # -------------------------------------------------------------------

        if should_auto_update(
            analysis
        ):

            search_query = (
                analysis.target_query.strip()
                or analysis.content
            )

            candidates = (
                retrieve_matching_memories(
                    query=search_query,
                    limit=10,
                )
            )

            print(
                "\n[Memory Manager: "
                "UPDATE CANDIDATES]"
            )

            if candidates:

                for candidate in candidates:

                    print(
                        f"ID "
                        f"{candidate['id']}: "
                        f"{candidate['content']}"
                    )

            else:

                print(
                    "No candidates found."
                )

            selection = (
                select_update_targets(
                    user_message=user_text,
                    new_content=analysis.content,
                    candidates=candidates,
                )
            )

            print(
                f"Selected IDs: "
                f"{selection.memory_ids}"
            )

            print(
                f"Selection confidence: "
                f"{selection.confidence}"
            )

            selected_ids = (
                selection.memory_ids

                if (
                    selection.confidence
                    >= 75
                )

                else []
            )

            new_id = store_memory(
                content=analysis.content,
                category=analysis.category,
                importance=analysis.importance,
                permanence=analysis.permanence,
                confidence=analysis.confidence,
                source="automatic",
            )

            if selected_ids:

                archived = (
                    archive_memories(
                        selected_ids,
                        reason="superseded",
                        superseded_by=new_id,
                    )
                )

                print(
                    "\n[Memory Manager: UPDATE]"
                )

                print(
                    f"Archived IDs: "
                    f"{archived}"
                )

                print(
                    f"New ID: {new_id}"
                )

                print(
                    f"New memory: "
                    f"{analysis.content}"
                )

            else:

                print(
                    "\n[Memory Manager: "
                    "UPDATE -> STORE]"
                )

                print(
                    "No old memory was "
                    "confidently matched."
                )

                print(
                    f"New ID: {new_id}"
                )

            return


        # -------------------------------------------------------------------
        # FORGET / ARCHIVE
        # -------------------------------------------------------------------

        if should_auto_delete(
            analysis
        ):

            candidates = (
                retrieve_matching_memories(
                    query=analysis.target_query,
                    limit=12,
                )
            )

            print(
                "\n[Memory Manager: "
                "FORGET CANDIDATES]"
            )

            if not candidates:

                print(
                    "No candidate "
                    "memories found."
                )

            else:

                for candidate in candidates:

                    print(
                        f"ID "
                        f"{candidate['id']}: "
                        f"{candidate['content']}"
                    )

            selection = (
                select_forget_targets(
                    user_message=user_text,
                    target_query=(
                        analysis.target_query
                    ),
                    candidates=candidates,
                )
            )

            print(
                f"Selected IDs: "
                f"{selection.memory_ids}"
            )

            print(
                f"Selection confidence: "
                f"{selection.confidence}"
            )

            if not selection.memory_ids:

                print(
                    "\n[Memory Manager: FORGET]"
                )

                print(
                    "No matching memories "
                    "were selected."
                )

                return


            # Candidate retrieval and model-based selection have
            # already occurred. This threshold protects against
            # ambiguous memory deletion.

            if selection.confidence < 65:

                print(
                    "\n[Memory Manager: FORGET]"
                )

                print(
                    "Memory selection confidence "
                    "was too low to modify storage."
                )

                return

            archived = archive_memories(
                selection.memory_ids,
                reason="forgotten",
            )

            print(
                "\n[Memory Manager: FORGET]"
            )

            print(
                f"Archived IDs: "
                f"{archived}"
            )

            return


    except Exception as error:

        # Memory failures must not crash P.E.P.P.E.R.

        print(
            "\n[Memory Manager Warning]"
        )

        print(
            error
        )


# ---------------------------------------------------------------------------
# Native Good Morning Protocol
# ---------------------------------------------------------------------------

def _is_good_morning_protocol_command(user_text: str) -> bool:
    normalized = " ".join(
        user_text.lower().strip().replace("-", " ").split()
    )

    for prefix in (
        "hey pepper ",
        "pepper ",
        "hey piper ",
        "piper ",
    ):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):].strip()
            break

    return normalized in {
        "run my good morning protocol",
        "run good morning protocol",
        "run the good morning protocol",
        "start my good morning protocol",
        "start good morning protocol",
        "good morning protocol",
    }


def handle_native_good_morning_protocol(user_text: str):
    if not _is_good_morning_protocol_command(user_text):
        return None

    print("[Native Protocol Route] good_morning")

    briefing = run_good_morning_protocol(
        surface=False,
    )

    return briefing.spoken_text


# ---------------------------------------------------------------------------
# Native Protocol Status
# ---------------------------------------------------------------------------

_PROTOCOL_STATUS_COMMANDS = {
    "what protocols are active", "what protocols are on",
    "which protocols are active", "which protocols are on",
    "what protocols do i have active", "what scheduled protocols do i have",
    "what protocols do i have", "list my protocols", "show my protocols",
}

def _normalize_protocol_status_command(user_text: str) -> str:
    text = " ".join(str(user_text).strip().lower().replace("?", "").replace(",", "").split())
    for prefix in ("hey pepper ", "pepper ", "hey piper ", "piper "):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    return text

def _is_protocol_status_command(user_text: str) -> bool:
    text = _normalize_protocol_status_command(user_text)
    if text in _PROTOCOL_STATUS_COMMANDS: return True
    return "protocol" in text and any(p in text for p in ("active", "turned on", "on right now", "scheduled", "do i have", "list", "show"))

def handle_native_protocol_status(user_text: str):
    if not _is_protocol_status_command(user_text): return None
    print("[Native Protocol Route] protocol_status")
    status = protocol_status(_GOOD_MORNING_SCHEDULER)
    if not status["enabled"]: return "You have no active scheduled protocols, sir."
    if status["running_now"]: return "The Good Morning Protocol is active and running right now, sir."
    hour, minute = status["local_time"].split(":")
    hour_number = int(hour)
    suffix = "AM" if hour_number < 12 else "PM"
    display_hour = hour_number % 12 or 12
    return f"You have one active protocol, sir. The Good Morning Protocol runs daily at {display_hour}:{minute} {suffix}."


# ---------------------------------------------------------------------------
# Generic Native Protocol Runner
# ---------------------------------------------------------------------------

from assistant.protocols.registry import PROTOCOL_REGISTRY

_PROTOCOL_RUNNERS = PROTOCOL_REGISTRY.runner_map()


def _normalize_protocol_run_command(user_text: str) -> str:
    text = " ".join(
        str(user_text)
        .strip()
        .lower()
        .replace("?", "")
        .split()
    )

    for prefix in (
        "hey pepper ",
        "pepper ",
        "hey piper ",
        "piper ",
    ):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break

    if "," in text:
        first, remainder = text.split(",", 1)
        if first and " " not in first.strip() and remainder.strip():
            text = remainder.strip()

    return text


def _parse_protocol_run_command(user_text: str):
    text = _normalize_protocol_run_command(user_text)
    for prefix in ('hey pepper ', 'pepper ', 'hey piper ', 'piper '):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    if ',' in text:
        _, remainder = text.split(',', 1)
        remainder = remainder.strip()
        if remainder.startswith(('run ', 'start ', 'execute ')):
            text = remainder
    verb = None
    for candidate in ('run', 'start', 'execute'):
        prefix = candidate + ' '
        if text.startswith(prefix):
            verb = candidate
            text = text[len(prefix):].strip()
            break
    if verb is None:
        return None
    for prefix in ('the ', 'my '):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    text = text.rstrip(' .!?').strip()
    suffixes = (' for me please',' please for me',' for me',' please')
    changed = True
    while changed:
        changed = False
        for suffix in suffixes:
            if text.endswith(suffix):
                text = text[:-len(suffix)].rstrip(' .!?').strip()
                changed = True
                break
    if text.endswith(' protocol'):
        text = text[:-len(' protocol')].strip()
    if text in _PROTOCOL_RUNNERS:
        return text
    return None



def handle_native_protocol_run(user_text: str):
    protocol_name = _parse_protocol_run_command(user_text)

    if protocol_name is None:
        return None

    runner = _PROTOCOL_RUNNERS.get(protocol_name)
    if runner is None:
        return f"I don't have an active {protocol_name} protocol, sir."

    print(f"[Native Protocol Route] run:{protocol_name}")

    spoken_text = str(runner() or "").strip()
    if not spoken_text:
        raise RuntimeError(
            f"{protocol_name} protocol returned no speech"
        )

    return spoken_text


# ---------------------------------------------------------------------------
# Process User Prompt
# ---------------------------------------------------------------------------

def complete_response(
    user_text: str,
    response: str,
):
    """
    Displays, stores, speaks, and records telemetry for one
    completed P.E.P.P.E.R. response.
    """

    mark(
        "response_ready"
    )

    print(
        f"\nP.E.P.P.E.R.: "
        f"{response}\n"
    )

    with span(
        "conversation_save"
    ):

        save_conversation(
            user_text,
            response,
        )

    mark(
        "tts_started"
    )

    try:

        with span(
            "tts_total"
        ):

            speak_response(
            user_text,
            response,
        )

    finally:

        mark(
            "speech_finished"
        )

        telemetry = (
            finish_request()
        )

        if telemetry is not None:

            persist_telemetry(
                telemetry
            )

            print_latency_report(
                telemetry
            )

        clear_request()

def process_prompt(
    user_text,
    *,
    voice_streaming: bool = False,
):
    """
    Shared P.E.P.P.E.R. processing pipeline.

    Priority:

        1. pending Phase 11 workflow approval
        2. pending integration account selection
        3. pending Phase 6 tool approval
        4. Phase 10 preference commands
        5. Phase 11 workflow / protocol commands
        6. Phase 7 agent continuation / new agent tasks
        7. explicit memory commands
        8. immediate Phase 6 tool actions
        9. intelligent memory
        10. normal reasoning

    Temporary integration account selections never reach long-term
    memory processing.
    """

    user_text = (
        user_text
        .strip()
    )


    if not user_text:

        return

    # -----------------------------------------------------------------------
    # Phase 14A - Request Telemetry
    # -----------------------------------------------------------------------

    start_request(
        user_text
    )

    mark(
        "request_received"
    )


    # -----------------------------------------------------------------------
    # Phase 14 - Immediate Cached Voice Acknowledgement
    # -----------------------------------------------------------------------
    #
    # Voice mode only.
    #
    # Plays a pre-generated acknowledgement immediately while the normal
    # frozen Phase 1-13 routing pipeline continues processing.
    #
    # Examples:
    #     "Got it, boss."
    #     "Checking."
    #     "On it."
    #     "Yes, boss."
    #
    # This uses cached WAV files, so it does not invoke F5-TTS or block
    # authoritative reasoning.
    # -----------------------------------------------------------------------

    if (
        voice_streaming
        and VOICE_ACKNOWLEDGEMENTS_ENABLED
    ):

        acknowledgement = (
            choose_acknowledgement()
        )

        if acknowledgement is not None:

            play_acknowledgement(
                acknowledgement,
                asynchronous=
                    True,
            )


    print(
        f"\nYou: {user_text}"
    )

    # -----------------------------------------------------------------------
    # Native Protocol Commands
    # -----------------------------------------------------------------------

    native_protocol_run_response = (
        handle_native_protocol_run(
            user_text
        )
    )

    if native_protocol_run_response is not None:

        complete_response(
            user_text,
            native_protocol_run_response,
        )

        return


    native_protocol_status_response = (
        handle_native_protocol_status(
            user_text
        )
    )

    if native_protocol_status_response is not None:

        complete_response(
            user_text,
            native_protocol_status_response,
        )

        return


    native_good_morning_response = (
        handle_native_good_morning_protocol(
            user_text
        )
    )

    if native_good_morning_response is not None:

        complete_response(
            user_text,
            native_good_morning_response,
        )

        return

    # -----------------------------------------------------------------------
    # Phase 11 - Pending Workflow Approval
    # -----------------------------------------------------------------------

    workflow_approval = (
        handle_pending_workflow_approval(
            user_text
        )
    )


    if workflow_approval.get(
        "handled",
        False,
    ):

        response = (
            workflow_approval.get(
                "response"
            )
            or "Done."
        )


        follow_up = (
            workflow_approval.get(
                "follow_up",
                ""
            )
            .strip()
        )


        complete_response(
            user_text,
            response,
        )


        if follow_up:

            process_prompt(
                follow_up,
                voice_streaming=
                    voice_streaming,
            )


        return

    # -----------------------------------------------------------------------
    # Pending Integration Account Selection
    # -----------------------------------------------------------------------

    from .brain import (
        handle_pending_integration_selection,
    )


    selection_result = (
        handle_pending_integration_selection(
            user_text
        )
    )


    if selection_result.get(
        "handled",
        False,
    ):

        response = (
            selection_result.get(
                "response"
            )
            or "Done."
        )


        follow_up = (
            selection_result.get(
                "follow_up",
                ""
            )
            .strip()
        )


        complete_response(
            user_text,
            response,
        )


        if follow_up:

            process_prompt(
                follow_up,
                voice_streaming=
                    voice_streaming,
            )


        return


    # -----------------------------------------------------------------------
    # Pending Phase 6 Tool Approval
    # -----------------------------------------------------------------------

    approval_result = (
        handle_pending_tool_approval(
            user_text
        )
    )


    if approval_result.get(
        "handled",
        False,
    ):

        response = (
            approval_result.get(
                "response"
            )
            or "Done."
        )


        follow_up = (
            approval_result.get(
                "follow_up",
                ""
            )
            .strip()
        )


        complete_response(
            user_text,
            response,
        )


        if follow_up:

            print(
                "\n[Tool Follow-Up]"
            )


            print(
                "Continuing with:",
                follow_up,
            )


            process_prompt(
                follow_up,
                voice_streaming=
                    voice_streaming,
            )


        return

    # -----------------------------------------------------------------------
    # Phase 10E - Explicit Preference Commands
    # -----------------------------------------------------------------------

    preference_response = (
        handle_preference_command(
            user_text
        )
    )


    if preference_response:

        complete_response(
            user_text,
            preference_response,
        )

        return

    # -----------------------------------------------------------------------
    # Phase 11 - Workflow / Protocol Commands
    # -----------------------------------------------------------------------

    with span(
        "phase11_workflow"
    ):

        workflow_result = (
            handle_workflow_message(
                user_text,
                default_timezone=
                    "America/Los_Angeles",
            )
        )


    if workflow_result.get(
        "handled",
        False,
    ):

        response = (
            workflow_result.get(
                "response"
            )
            or "Done."
        )


        follow_up = (
            workflow_result.get(
                "follow_up",
                ""
            )
            .strip()
        )


        complete_response(
            user_text,
            response,
        )


        if follow_up:

            process_prompt(
                follow_up,
                voice_streaming=
                    voice_streaming,
            )


        return

    # -----------------------------------------------------------------------
    # Phase 15 - System Health, Diagnostics & Self-Awareness
    # -----------------------------------------------------------------------

    with span(
        "phase15_system"
    ):

        system_result = (
            handle_system_message(
                user_text
            )
        )


    if system_result.get(
        "handled",
        False,
    ):

        response = (
            system_result.get(
                "response"
            )
            or "Done."
        )


        follow_up = (
            system_result.get(
                "follow_up",
                ""
            )
            .strip()
        )


        complete_response(
            user_text,
            response,
        )


        if follow_up:

            process_prompt(
                follow_up,
                voice_streaming=
                    voice_streaming,
            )


        return


    # -----------------------------------------------------------------------
    # Phase 12N - Self-Engineering Integration
    # -----------------------------------------------------------------------
    #
    # Explicit repository/self-engineering requests are routed here.
    #
    # Safety flow:
    #
    #     request
    #         ↓
    #     read-only discovery
    #         ↓
    #     bounded engineering plan
    #         ↓
    #     execution approval
    #         ↓
    #     branch / edit / validation / regression
    #         ↓
    #     commit approval
    #
    # Ordinary conversation continues through memory/tools/reasoning.
    # -----------------------------------------------------------------------

    with span(
        "phase12_coding"
    ):

        coding_result = (
            handle_coding_message(
                user_text
            )
        )


    if coding_result.get(
        "handled",
        False,
    ):

        response = (
            coding_result.get(
                "response"
            )
            or "Done."
        )


        follow_up = (
            coding_result.get(
                "follow_up",
                ""
            )
            .strip()
        )


        complete_response(
            user_text,
            response,
        )


        if follow_up:

            process_prompt(
                follow_up,
                voice_streaming=
                    voice_streaming,
            )


        return
    
    # -----------------------------------------------------------------------
    # Phase 7 Unified Agent Routing / Continuation
    # -----------------------------------------------------------------------
    #
    # handle_agent_message() is the single Phase 7 entry point. It handles
    # active-task continuation/approval and new multi-step agent requests,
    # then yields back to Phase 6 / memory / reasoning when not handled.
    # -----------------------------------------------------------------------

    try:

        from .agent.integration import (
            handle_agent_message,
        )


        with span(
            "phase7_agent"
        ):

            agent_result = (
                handle_agent_message(
                    user_text
                )
            )


        if (
            isinstance(
                agent_result,
                dict,
            )
            and agent_result.get(
                "handled",
                False,
            )
        ):

            response = (
                agent_result.get(
                    "response"
                )
                or "Done."
            )


            complete_response(
                user_text,
                response,
            )


            follow_up = (
                agent_result.get(
                    "follow_up",
                    ""
                )
                .strip()
            )


            if follow_up:

                process_prompt(
                follow_up,
                voice_streaming=
                    voice_streaming,
            )


            return


    except (
        ImportError,
        AttributeError,
    ):

        # Current Phase 7 installation may expose its runtime through
        # another path. Continue into the existing normal pipeline.
        pass


    # -----------------------------------------------------------------------
    # Phase 13L - Computer & Device Control Integration
    # -----------------------------------------------------------------------

    with span(
        "phase13_computer"
    ):

        computer_result = (
            handle_computer_message(
                user_text
            )
        )

    if computer_result.get(
        "handled",
        False,
    ):

        response = (
            computer_result.get(
                "response"
            )
            or "Done."
        )

        complete_response(
            user_text,
            response,
        )

        return
    
    # -----------------------------------------------------------------------
    # Explicit Memory
    # -----------------------------------------------------------------------

    if handle_manual_memory(
        user_text
    ):

        return


    # -----------------------------------------------------------------------
    # Immediate Phase 6 Tool Request
    # -----------------------------------------------------------------------

    with span(
        "phase6_tool_routing"
    ):

        tool_result = (
            handle_tool_request(
                user_text
            )
        )

    if tool_result.get(
        "handled",
        False,
    ):

        response = (
            tool_result.get(
                "response"
            )
            or (
                "I processed the requested "
                "computer action."
            )
        )


        complete_response(
            user_text,
            response,
        )


        return


    # -----------------------------------------------------------------------
    # Phase 16C - Deterministic Conversational Fast Path
    # -----------------------------------------------------------------------
    #
    # IMPORTANT:
    # This sits AFTER all existing approval/workflow/system/agent/computer/
    # tool routing, so it cannot steal commands such as "okay" or "approved"
    # from frozen Phase 1-15 continuation logic.
    # -----------------------------------------------------------------------

    phase16_fast_conversation = (
        handle_fast_conversation(
            user_text
        )
    )


    if phase16_fast_conversation.handled:

        complete_response(
            user_text,
            phase16_fast_conversation.response,
        )

        return


    # -----------------------------------------------------------------------
    # Intelligent Memory
    # -----------------------------------------------------------------------

    phase16_cost_profile = classify_request_cost(user_text)

    with span(
        "memory_processing"
    ):
        if phase16_cost_profile.run_intelligent_memory:
            process_intelligent_memory(
                user_text
            )


    # -----------------------------------------------------------------------
    # Main Reasoning
    # -----------------------------------------------------------------------

    phase16_performance_context = performance_request_context(
        allow_long_term_memory=phase16_cost_profile.allow_long_term_memory,
        allow_project_knowledge=phase16_cost_profile.allow_project_knowledge,
        reason=phase16_cost_profile.reason,
    )

    with phase16_performance_context:
        if voice_streaming:

            # -------------------------------------------------------------------
            # Phase 14 - Perceived Latency Telemetry
            # -------------------------------------------------------------------

            first_sentence_marked = False
            first_audio_marked = False

            # Telemetry only: measure existing speech-pipeline events.
            from time import perf_counter as _speech_metric_now

            speech_synthesis_started = {}
            speech_playback_started = {}

            speech_generation_total = 0.0
            speech_playback_total = 0.0

            speech_pipeline_started_at = None
            speech_pipeline_finished_at = None


            def handle_authoritative_sentence(
                sentence,
            ):

                nonlocal first_sentence_marked


                if not first_sentence_marked:

                    mark(
                        "first_authoritative_sentence"
                    )

                    first_sentence_marked = True


                return (
                    speech_pipeline.submit_sentence(
                        sentence
                    )
                )


            def handle_authoritative_speech_event(
                event,
            ):

                nonlocal first_audio_marked
                nonlocal speech_generation_total
                nonlocal speech_playback_total
                nonlocal speech_pipeline_started_at
                nonlocal speech_pipeline_finished_at

                now = _speech_metric_now()

                if (
                    event.kind
                    == "playback_started"

                    and not first_audio_marked
                ):

                    mark(
                        "first_audio_started"
                    )

                    first_audio_marked = True

                if event.kind == "synthesis_started":

                    speech_synthesis_started[
                        event.index
                    ] = now

                    if speech_pipeline_started_at is None:
                        speech_pipeline_started_at = now

                elif event.kind == "synthesis_finished":

                    started = speech_synthesis_started.pop(
                        event.index,
                        None,
                    )

                    if started is not None:
                        speech_generation_total += max(
                            0.0,
                            now - started,
                        )

                elif event.kind == "playback_started":

                    speech_playback_started[
                        event.index
                    ] = now

                elif event.kind == "playback_finished":

                    started = speech_playback_started.pop(
                        event.index,
                        None,
                    )

                    if started is not None:
                        speech_playback_total += max(
                            0.0,
                            now - started,
                        )

                    speech_pipeline_finished_at = now


            # -------------------------------------------------------------------
            # Authoritative Streaming Speech Pipeline
            # -------------------------------------------------------------------

            speech_pipeline = (
                AuthoritativeSpeechPipeline(
                    synthesize_fn=
                        synthesize_audio,

                    play_fn=
                        play_audio,

                    prepare_fn=
                        prepare_spoken_text,

                    emit_fn=
                        handle_authoritative_speech_event,

                    max_sentences=
                        2,

                    max_characters=
                        340,

                    rolling=
                        True,
                )
            )


            speech_pipeline.start()


            # -------------------------------------------------------------------
            # Authoritative Streaming Reasoning
            # -------------------------------------------------------------------

            with span(
                "reasoning"
            ):

                phase16_context_budget = (
                    context_budget_for_profile(
                        phase16_cost_profile
                    )
                )


                contextual_user_text = (
                    build_contextual_expansion_prompt(
                        user_text
                    )
                )


                contextual_user_text = (
                    augment_with_project_evidence(
                        contextual_user_text,
                        allow_project_knowledge=(
                            phase16_cost_profile
                            .allow_project_knowledge
                        ),
                        limit=(
                            phase16_context_budget
                            .project_items
                        ),
                        max_characters=(
                            phase16_context_budget
                            .project_characters
                        ),
                    )
                )


                reasoning_text = (
                    apply_response_length_policy(
                        contextual_user_text,
                        voice_mode=
                            True,
                    )
                )


                use_fast_reasoning = (
                    should_use_fast_voice_reasoning(
                        user_text,
                        phase16_cost_profile,
                    )
                )


                if use_fast_reasoning:

                    print(
                        "[Reasoning Route] "
                        "fast conversational model"
                    )


                    try:

                        response = (
                            stream_fast_authoritative_chat(
                                reasoning_text,

                                on_sentence=
                                    handle_authoritative_sentence,
                            )
                        )


                    except Exception as error:

                        # Phase 16F is an optimization only.
                        # Any fast-model/API failure falls back to the
                        # already-certified authoritative reasoning path.
                        print(
                            (
                                "[Reasoning Route Warning] "
                                "Fast route failed; "
                                "using authoritative fallback: "
                                f"{error}"
                            )
                        )


                        response = (
                            stream_authoritative_chat(
                                reasoning_text,

                                on_sentence=
                                    handle_authoritative_sentence,
                            )
                        )


                else:

                    response = (
                        stream_authoritative_chat(
                            reasoning_text,

                            on_sentence=
                                handle_authoritative_sentence,
                        )
                    )


            speech_pipeline.finish_input()


            mark(
                "response_ready"
            )


            print(
                f"\nP.E.P.P.E.R.: "
                f"{response}\n"
            )


            with span(
                "conversation_save"
            ):

                save_conversation(
                    user_text,
                    response,
                )


            mark(
                "tts_started"
            )


            with span(
                "tts_total"
            ):

                speech_pipeline.wait()


            mark(
                "speech_finished"
            )


            telemetry = (
                finish_request()
            )


            if telemetry is not None:

                persist_telemetry(
                    telemetry
                )

                print_latency_report(
                    telemetry
                )

                speech_pipeline_wall = None

                if (
                    speech_pipeline_started_at is not None
                    and speech_pipeline_finished_at is not None
                ):
                    speech_pipeline_wall = max(
                        0.0,
                        speech_pipeline_finished_at
                        - speech_pipeline_started_at,
                    )

                print()
                print("[Speech Timing]")
                print(
                    "tts_generation_total: "
                    f"{speech_generation_total:.3f}s"
                )
                print(
                    "speech_playback_total: "
                    f"{speech_playback_total:.3f}s"
                )

                if speech_pipeline_wall is not None:
                    print(
                        "speech_pipeline_wall: "
                        f"{speech_pipeline_wall:.3f}s"
                    )


            clear_request()


        else:

            with span(
                "reasoning"
            ):

                response = chat(
                    user_text
                )


            complete_response(
                user_text,
                response,
            )

# ---------------------------------------------------------------------------
# Phase 14 - Voice Authoritative Streaming Entry
# ---------------------------------------------------------------------------

def process_voice_prompt(
    user_text,
):
    """
    Processes finalized voice requests through the normal frozen
    P.E.P.P.E.R. routing architecture while enabling authoritative
    sentence-by-sentence streaming for normal reasoning.
    """

    return (
        process_prompt(
            user_text,

            voice_streaming=
                True,
        )
    )

# ---------------------------------------------------------------------------
# Phase 14 - Wake Voice Authentication Speech
# ---------------------------------------------------------------------------

def speak_authenticated_wake():
    """
    Speaks the wake authentication greeting.

    This greeting itself acts as the immediate acknowledgement for
    the inline wake request, so the next cached acknowledgement is
    suppressed.
    """

    suppress_next_acknowledgement()


    line = (
        authenticated_wake_line()
    )


    print(
        f"P.E.P.P.E.R.: {line}"
    )


    speak(
        line
    )

def speak_unrecognized_wake():
    """
    Speaks the unrecognized-voice notice.

    This is already an immediate spoken response, so a cached
    acknowledgement should not follow it either.
    """

    suppress_next_acknowledgement()


    print(
        f"P.E.P.P.E.R.: {NOT_RECOGNIZED_LINE}"
    )


    speak(
        NOT_RECOGNIZED_LINE
    )


# ---------------------------------------------------------------------------
# Automatic Good Morning Scheduler
# ---------------------------------------------------------------------------

_GOOD_MORNING_SCHEDULER = None


def _scheduled_good_morning_delivery():
    briefing = run_good_morning_protocol(
        surface=False,
    )
    spoken_text = str(
        briefing.spoken_text
        or ""
    ).strip()
    if not spoken_text:
        raise RuntimeError(
            "Good Morning Protocol returned no spoken text."
        )
    print(
        f"\nP.E.P.P.E.R.: {spoken_text}\n"
    )
    speak_response(
        "scheduled good morning protocol",
        spoken_text,
    )


def start_good_morning_scheduler(
    *,
    is_busy_fn=None,
    deliver_fn=None,
):
    global _GOOD_MORNING_SCHEDULER

    if (
        _GOOD_MORNING_SCHEDULER is not None
        and _GOOD_MORNING_SCHEDULER.running
    ):
        return _GOOD_MORNING_SCHEDULER

    _GOOD_MORNING_SCHEDULER = GoodMorningScheduler(
        deliver_fn=(
            deliver_fn
            or _scheduled_good_morning_delivery
        ),
        is_busy_fn=is_busy_fn,
        hour=7,
        minute=0,
    )
    _GOOD_MORNING_SCHEDULER.start()
    return _GOOD_MORNING_SCHEDULER


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

init_memory()


print(
    "Preparing semantic memory..."
)


missing_embeddings = (
    sync_memory_embeddings()
)


if missing_embeddings:

    print(
        f"Generated "
        f"{missing_embeddings} "
        f"missing memory embeddings."
    )


# Phase 16A - non-blocking semantic-model warmup.
start_background_prewarm(
    delay_seconds=1.0
)


# Phase 16E - non-blocking first-inference F5 warmup.
start_tts_prewarm()


# Automatic 7:00 AM local Good Morning Protocol.
start_good_morning_scheduler()

print(
    "\nP.E.P.P.E.R. Online"
)


print(
    "-------------------------"
)


print(
    "[T] Terminal"
)


print(
    "[V] Voice"
)


print(
    "[Q] Quit"
)


print(
    "-------------------------"
)


# ---------------------------------------------------------------------------
# Main Application Loop
# ---------------------------------------------------------------------------

while True:

    mode = input(
        "\nMode: "
    ).strip().lower()


    # -----------------------------------------------------------------------
    # Quit
    # -----------------------------------------------------------------------

    if mode in {
        "q",
        "quit",
        "exit",
    }:

        print(
            "\nP.E.P.P.E.R. Offline"
        )

        break


    # -----------------------------------------------------------------------
    # Terminal Input
    # -----------------------------------------------------------------------

    elif mode in {
        "t",
        "terminal",
    }:

        user_text = input(
            "You: "
        ).strip()

        if user_text.lower() in {
            "quit",
            "exit",
        }:

            print(
                "\nP.E.P.P.E.R. Offline"
            )

            break

        process_prompt(
            user_text
        )


    # -----------------------------------------------------------------------
    # Voice Input
    # -----------------------------------------------------------------------

    elif mode in {
        "v",
        "voice",
    }:

        voice_result = (
            run_voice_session(
                listen_fn=
                    listen,

                process_prompt_fn=
                    process_voice_prompt,

                interrupt_speech_fn=
                    stop_audio,

                pause_speech_fn=
                    pause_audio,

                resume_speech_fn=
                    resume_audio,

                speech_started_fn=
                    pause_audio,

                require_wake=
                    True,

                wake_authenticate_fn=
                    authenticate_last_wake_utterance,

                wake_authenticated_fn=
                    speak_authenticated_wake,

                wake_unrecognized_fn=
                    speak_unrecognized_wake,
            )
        )


        if voice_result.quit_application:

            break

    # -----------------------------------------------------------------------
    # Invalid Input
    # -----------------------------------------------------------------------

    else:

        print(
            "\nChoose T for terminal, "
            "V for voice, or Q to quit."
        )