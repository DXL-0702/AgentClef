# Technology Stack

## Frontend

| Layer | Technology | Role |
| :--- | :--- | :--- |
| UI runtime | React + TypeScript | Workbench application and typed UI state |
| Build tool | Vite | Fast local development and production bundle |
| Server state | TanStack Query | API data fetching, caching, invalidation, loading states |
| Client state | Zustand | Workbench-local selection, editor state, UI state |
| Styling | Tailwind CSS | Utility-first styling for dense workbench UI |
| Waveform | wavesurfer.js | Audio waveform, regions, timeline interaction |
| Notation rendering | VexFlow | Future standard notation rendering path |

v0.1 uses a piano-roll-like timeline editor as the primary editable score view. Standard notation rendering is introduced after the transcription review loop is stable.

## Backend

| Layer | Technology | Role |
| :--- | :--- | :--- |
| Language | Python 3.12+ | Audio, model, and backend ecosystem alignment |
| API framework | FastAPI | Typed REST API and OpenAPI contract |
| Schema validation | Pydantic | Request, response, DraftScore, Agent output validation |
| ORM | SQLAlchemy | Database model and persistence layer |
| Migration | Alembic | Database schema evolution |
| Database | PostgreSQL | Project, task, score, Agent, edit, and revision persistence |
| Queue broker | Redis | Celery broker and short-lived task state |
| Task worker | Celery | Audio processing, transcription, postprocessing, export jobs |

## Audio and Music Pipeline

| Layer | Technology | Role |
| :--- | :--- | :--- |
| Audio normalization | FFmpeg | Format conversion and standardization |
| Audio analysis | librosa | Beat, onset, tempo, and feature utilities |
| AMT baseline | Basic Pitch | Initial monophonic/polyphonic note event baseline |
| Symbolic music | music21 / pretty_midi | MIDI, MusicXML, and symbolic music utilities |

Basic Pitch is the v0.1 baseline AMT adapter. The architecture keeps model adapters replaceable for later evaluation.

## LLM Layer

| Layer | Technology | Role |
| :--- | :--- | :--- |
| Provider boundary | LLM provider adapter | Isolates model vendor from product logic |
| Output validation | Pydantic / JSON Schema | Ensures Agent output matches CandidateEdit protocol |
| Context source | DraftScore + SelectionRange | Keeps Agent reasoning grounded in current score state |

LLM providers are not embedded directly in business logic. Agent output is treated as a proposal source and is never applied without system validation and user confirmation.

## Quality Tooling

| Area | Tooling |
| :--- | :--- |
| Backend tests | pytest |
| Backend lint / format | ruff |
| Backend typing | mypy or pyright |
| Frontend tests | Vitest |
| E2E tests | Playwright |
| Schema contracts | Pydantic / JSON Schema tests |
| Pipeline regression | Fixed audio fixtures and DraftScore golden tests |

## Repository Shape

Target structure:

```text
AgentClef/
├── docs/
├── server/              # FastAPI backend
├── worker/              # Celery tasks and audio pipeline
├── web/                 # React + Vite workbench
├── shared/              # Shared schema definitions or generated contracts
├── tests/
└── docker-compose.yml
```
