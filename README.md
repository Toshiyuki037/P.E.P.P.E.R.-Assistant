<a id="readme-top"></a>

<!-- BADGES -->

<p align="center">
  <img src="https://img.shields.io/badge/AI-Agentic%20System-blue?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Voice-Real--Time-green?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Vision-Multimodal-orange?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Python-3.11-yellow?style=for-the-badge" />
</p>

<br />

<!-- TITLE -->

<div align="center">

# P.E.P.P.E.R.

### Personal Engineering Partner for People Eventually Replaced

A multimodal AI engineering assistant that can see my work, understand project context, reason through technical problems, and take actions on my computer with permission.

<br />

**[🎥 View Demo](YOUR_DEMO_LINK_HERE)**

</div>

---

## Overview

P.E.P.P.E.R. is a persistent AI engineering assistant built to move beyond the traditional chatbot workflow.

Instead of requiring every problem to be manually copied into an AI interface, P.E.P.P.E.R. can combine voice, vision, workspace context, persistent memory, tools, and multi-step agent execution to work alongside me directly.

It can inspect engineering work, reason about problems, navigate the local development environment, modify files with authorization, execute tools, and verify the result.

The goal is simple:

> **Turn AI from something I interact with into something I can work alongside.**

---

## Demo

P.E.P.P.E.R. V2 demonstrates an end-to-end engineering workflow:

```text
SEE
 ↓
UNDERSTAND
 ↓
REASON
 ↓
NAVIGATE
 ↓
DIAGNOSE
 ↓
REQUEST PERMISSION
 ↓
ACT
 ↓
VERIFY
```

In the current demonstration, P.E.P.P.E.R. can:

- Visually inspect a circuit-analysis problem
- Identify an incorrect KCL equation
- Open a requested engineering workspace in VS Code
- Locate and inspect a malfunctioning controller
- Diagnose the underlying control-logic error
- Request authorization before modifying the file
- Apply the correction
- Execute the program and verify the result

All through a continuous voice interaction.

---

## System Architecture

```text
                         USER
                           │
                 ┌─────────┴─────────┐
                 │                   │
               Voice               Vision
                 │                   │
                 └─────────┬─────────┘
                           ↓
                  Context / Perception
                           │
                           ↓
                 Memory + World State
                           │
                           ↓
                  Reasoning / Planning
                           │
                    ┌──────┴──────┐
                    │             │
               Direct Tools   Agent System
                    │             │
                    └──────┬──────┘
                           ↓
                Permission / Security
                           │
                           ↓
                       Execution
                           │
                           ↓
                     Verification
                           │
                           ↓
                   Voice + HUD Response
```

P.E.P.P.E.R. deliberately separates **intelligence from authority**.

The AI can determine what should happen, but deterministic software controls what it is allowed to do, how actions are executed, and whether the result is successfully verified.

This allows increasingly capable models to be integrated without giving the model unrestricted control of the computer.

---

## Core Capabilities

### Voice Interaction

P.E.P.P.E.R. includes a persistent voice runtime designed for natural hands-free interaction.

- Wake-word activation
- Voice activity detection
- Streaming and final transcription
- Voice identity authentication
- Context-aware follow-up conversation
- Local neural text-to-speech
- Low-latency acknowledgement responses
- Real-time visual HUD
- Spoken-response formatting optimized separately from full reasoning output

---

### Vision & Workspace Awareness

P.E.P.P.E.R. can reason about what I am currently working on rather than relying exclusively on manually supplied text.

Capabilities include:

- Screenshot and visual-input understanding
- Engineering-diagram analysis
- Active workspace awareness
- Application context
- File and repository awareness
- Visual fallback when structured interfaces are unavailable

Vision complements the deterministic control stack rather than replacing it.

---

### Persistent Memory

P.E.P.P.E.R. maintains long-term semantic memory across interactions.

The memory system supports:

- User preferences
- Project knowledge
- Conversation history
- Semantic retrieval
- Embedding search
- Reranking
- Importance and confidence
- Memory updates
- Supersession
- Duplicate detection
- Intentional memory formation

This allows relevant context to persist beyond an individual prompt or conversation.

---

### Agentic Execution

Complex requests can be converted into multi-step execution plans.

```text
User Goal
   ↓
Plan
   ↓
Execute Step
   ↓
Observe Result
   ↓
Verify
   ↓
Replan if Necessary
   ↓
Continue / Request Approval / Complete
```

The agent system supports:

- Goal decomposition
- Multi-step execution
- Persistent task state
- Tool selection
- Retry logic
- Replanning
- Approval checkpoints
- Failure recovery
- Result verification
- Resume and cancellation behavior

---

### Computer Control

P.E.P.P.E.R. interacts with the local environment through structured tools rather than unrestricted model access.

Current capabilities include:

- File operations
- Workspace search
- Application launching
- VS Code interaction
- Terminal execution
- Git operations
- Window control
- Browser interaction
- Keyboard actions
- Visual fallback
- Execution verification

The architecture prioritizes deterministic interfaces whenever possible.

---

## Security & Authorization

P.E.P.P.E.R. is designed around a simple principle:

> **Intelligence does not imply authority.**

Actions can be governed using:

```text
Voice Identity
      +
Session State
      +
Tool Permissions
      +
Risk Classification
      +
Explicit Approval
```

Read-only operations can execute with minimal friction, while state-changing or sensitive actions can require explicit authorization.

This allows P.E.P.P.E.R. to perform useful autonomous work without simply giving an LLM unrestricted computer access.

---

## HUD

P.E.P.P.E.R. includes a lightweight heads-up display for real-time interaction.

The HUD provides:

- Live response text
- Typewriter-synchronized output
- Audio-reactive visualization
- Persistent top-level overlay
- Automatic response lifecycle
- Minimal interference with the active workspace

The goal is to keep interaction visible without turning P.E.P.P.E.R. into a traditional chat window.

---

## Technology

P.E.P.P.E.R. currently uses technologies including:

- Python 3.11
- PyTorch
- NVIDIA CUDA
- Faster-Whisper
- Local neural TTS
- Semantic embedding models
- Reranking models
- PySide6 / Qt WebEngine
- Playwright
- REST APIs
- Git
- Windows system interfaces

The architecture is intentionally model-agnostic. Reasoning, vision, speech, and specialist models can be replaced or upgraded without rebuilding the surrounding memory, security, tool, and execution systems.

---

## Project Structure

```text
pepper-assistant/
│
├── assistant/
│   ├── cognition/          # reasoning, planning, agent execution
│   ├── interaction/        # voice, perception, presentation
│   ├── capabilities/       # tools and computer interfaces
│   ├── memory/             # persistent semantic memory
│   ├── observability/      # telemetry and performance
│   └── main.py             # primary runtime
│
├── pepper_hud/             # real-time visual interface
├── pepper-voice/           # voice resources
└── requirements.txt
```

---

## Design Philosophy

P.E.P.P.E.R. is not built around a single AI model.

The model is one component inside a larger system.

```text
                     P.E.P.P.E.R.
                          │
                  Intelligence Layer
                          │
           ┌──────────────┼──────────────┐
           │              │              │
       Reasoning        Vision       Specialist
         Model          Model          Models
           │              │              │
           └──────────────┼──────────────┘
                          ↓
                  P.E.P.P.E.R. Core
                          │
        Memory / Context / Tools / Security
                          │
                  Agent / Execution
                          │
                     Verification
```

Models can change.

Interfaces can change.

Hardware can change.

The underlying assistant architecture remains.

---

## V2 Status

**P.E.P.P.E.R. V2 — Multimodal Engineering Assistant**

Current V2 development establishes:

- [x] Persistent voice interaction
- [x] Voice authentication
- [x] Long-term semantic memory
- [x] Visual engineering reasoning
- [x] Workspace awareness
- [x] Multi-step agent execution
- [x] Permission-gated actions
- [x] File inspection and modification
- [x] Execution verification
- [x] VS Code integration
- [x] Real-time HUD
- [x] Performance telemetry
- [x] Failure handling and task isolation

---

## Roadmap

Future development focuses on making P.E.P.P.E.R. increasingly persistent, capable, and hardware-independent.

- [ ] Improved conversational state and intent tracking
- [ ] More robust autonomous task execution
- [ ] Local / self-hosted reasoning models
- [ ] Intelligent model routing
- [ ] Dedicated inference server
- [ ] Multi-device synchronization
- [ ] Proactive background monitoring
- [ ] Expanded engineering tools
- [ ] Improved application control
- [ ] Full-duplex voice interaction
- [ ] Acoustic echo cancellation
- [ ] Remote P.E.P.P.E.R. clients
- [ ] Embedded and wearable interfaces
- [ ] Long-duration reliability testing

---

## Documentation

Detailed architecture, development history, experiments, testing, and design decisions are maintained separately:

**[P.E.P.P.E.R. Full Project Documentation](YOUR_NOTION_LINK_HERE)**

---

## Why I Built It

Most AI systems are extremely capable once the user gives them the right information.

The friction is everything around that intelligence: supplying context, moving between applications, copying code and errors, executing suggestions, and returning the results.

P.E.P.P.E.R. is my attempt to remove that boundary.

Rather than repeatedly describing my engineering environment to an AI, I want the AI to understand that environment, reason within it, and safely work alongside me.

---

## License

Distributed under the MIT License.

---

## Contact

GitHub: https://github.com/Toshiyuki037

Project Repository:  
https://github.com/Toshiyuki037/pepper-assistant

---

<p align="center">
  <a href="#readme-top">↑ Back to top</a>
</p>
