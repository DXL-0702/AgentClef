<div align="center">

# AgentClef

**Audio is Evidence. Score is State.**

An AI Agent assisted transcription review workbench that turns audio into an editable draft score, then helps musicians reason, correct, and confirm every uncertain passage.

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-TypeScript-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-646CFF?style=flat-square&logo=vite&logoColor=white)](https://vite.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-DC382D?style=flat-square&logo=redis&logoColor=white)](https://redis.io)
[![Status](https://img.shields.io/badge/Status-v0.1_Planning-blue?style=flat-square)](./docs/v0.1/)

[English](README.md) · [简体中文](README.zh-CN.md) · [Docs](./docs/README.md) · [Architecture](./docs/technical-architecture.md) · [v0.1](./docs/v0.1/)

</div>

---

## Why AgentClef?

AI transcription tools are getting better at producing a first draft. The hard part is turning that draft into a score a musician can trust.

AgentClef is designed around the review loop after the first transcription pass: listen, inspect, ask, compare, edit, confirm.

| Problem | One-shot AI Transcription | AgentClef |
| :--- | :--- | :--- |
| Uncertain rhythm | Hidden inside the generated result | Exposed as local review targets |
| Wrong note duration | User manually guesses and edits | Agent reasons from audio evidence and beat context |
| AI edits | Often opaque or destructive | Proposed as CandidateEdits and applied only after confirmation |
| Score state | Export files or model output | Structured DraftScore as system truth |
| Accuracy goal | First-pass model accuracy | Final confirmed score accuracy |

## Core Philosophy

- **Evidence before notation** — every musical event should be traceable back to audio time and beat position.
- **Draft as structured state** — the internal score is not a PDF, image, or plain MIDI dump; it is an editable DraftScore.
- **Agent as reviewer, not owner** — the Agent explains and proposes edits, while the system owns score state and the user confirms changes.
- **Local reasoning over global guessing** — users select a note, measure, chord, or time range; the Agent reasons over that local musical context.
- **Accuracy through review** — AgentClef measures success by how quickly users reach a correct final score, not only by the first generated draft.

## Architecture

This is a high-level architecture snapshot. The full system design lives in [docs/technical-architecture.md](./docs/technical-architecture.md).

```
┌─────────────────────────────────────────────────────────────────┐
│                        Musician Workflow                        │
│   upload audio → draft score → local review → confirmed score   │
└────────────────────────────┬────────────────────────────────────┘
                             │
              ┌──────────────▼──────────────┐
              │     React + Vite Workbench   │
              │ waveform · note timeline ·   │
              │ Agent panel · edit preview   │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │       FastAPI Backend        │
              │ project · task · draft ·     │
              │ Agent context · edit engine  │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │     PostgreSQL + Redis       │
              │ DraftScore · revisions ·     │
              │ job queue · task state       │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │       Celery Worker          │
              │ audio normalize → timing     │
              │ AMT adapter → postprocess    │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │      LLM Provider Adapter    │
              │ local context → structured   │
              │ CandidateEdit proposals      │
              └─────────────────────────────┘
```

## Tech Stack

Full stack responsibilities are documented in [docs/technology-stack.md](./docs/technology-stack.md).

| Area | Stack |
| :--- | :--- |
| **Workbench** | React + TypeScript + Vite |
| **Frontend State** | TanStack Query + Zustand |
| **Backend** | Python 3.12+ + FastAPI + Pydantic |
| **Persistence** | PostgreSQL + SQLAlchemy + Alembic |
| **Jobs** | Redis + Celery |
| **Audio / Agent** | FFmpeg boundary + AMT adapter + LLM provider adapter |

## Workflow Preview

```text
1. Upload a local audio file
   → AgentClef creates a Project, AudioAsset, and TranscriptionJob

2. Generate a structured draft
   → the worker builds BeatGrid, NoteEvents, optional ChordEvents, and uncertainty markers

3. Review inside the workbench
   → waveform and editable note timeline stay aligned around the same DraftScore

4. Ask the Agent about a local passage
   → "How long should this high note last?"

5. Confirm a CandidateEdit
   → the Edit Engine validates the proposal, updates DraftScore, and writes a Revision
```

## Project Structure

Target v0.1 structure:

```
AgentClef/
├── docs/        # product, architecture, model, and milestone documentation
├── server/      # FastAPI backend
├── worker/      # Celery tasks and audio pipeline
├── web/         # React + Vite workbench
├── shared/      # shared schema contracts or generated types
└── tests/       # backend, pipeline, contract, and E2E tests
```

`AGENTS.md` is a local collaboration instruction file and is not part of the public project documentation.

## Roadmap

| Milestone | Status | Focus |
| :--- | :--- | :--- |
| **v0.1** | Planning | Local audio upload, async draft generation, timeline review, Agent CandidateEdit confirmation |
| **v0.2** | Planned | Audio-score synchronization, loop playback, uncertainty navigation, candidate comparison |
| **v0.3** | Planned | Accuracy fixtures, model adapter evaluation, beat and quantization improvements |
| **v0.4** | Planned | Project lifecycle, revision browsing, MIDI and MusicXML export baseline |
| **v0.5** | Planned | Chord timeline, transposition, instrument modes, stem-assisted review research |
| **v1.0** | Planned | Stable AI Agent transcription review workbench |

## Development

> AgentClef is currently in the v0.1 planning-to-implementation stage. The commands below describe the target local development flow after the foundation issue is implemented.

```bash
# Backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn server.main:app --reload

# Worker
celery -A worker.app:celery_app worker --loglevel=info

# Frontend
cd web
npm install
npm run dev
```

Quality gates:

```bash
# Backend
pytest
ruff check .

# Frontend
npm run test
npm run build

# E2E
npx playwright test
```

## Documentation

- [Product Positioning](./docs/product-positioning.md)
- [Technical Architecture](./docs/technical-architecture.md)
- [Technology Stack](./docs/technology-stack.md)
- [Data Model](./docs/data-model.md)
- [Agent Edit Protocol](./docs/agent-edit-protocol.md)
- [Accuracy Strategy](./docs/accuracy-strategy.md)
- [Competitive Insights](./docs/competitive-insights.md)
- [v0.1 Architecture](./docs/v0.1/architecture.md)

## Development Process

AgentClef uses issue-scoped development. Local collaboration instructions are kept in `AGENTS.md`, which is intentionally excluded from public documentation.

1. Confirm the issue objective, scope, implementation points, tests, and acceptance criteria before coding.
2. Implement only within the confirmed issue boundary.
3. Run local quality gates before handing off.
4. Use Conventional Commits.
5. The developer performs `git commit` and `git push`.

## Current Development Version

AgentClef is currently in **v0.1**: the minimum transcription review loop.

- [v0.1 Documentation](./docs/v0.1/)
- [v0.1 Architecture](./docs/v0.1/architecture.md)

---

<div align="center">

**AgentClef** — make every uncertain note reviewable.

</div>
