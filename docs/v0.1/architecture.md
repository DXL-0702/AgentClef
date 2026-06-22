# AgentClef v0.1 Architecture

> Milestone: `v0.1-transcription-review-loop`
>
> Stage goal: implement the minimum audio-to-draft-to-Agent-review loop.
>
> Stage boundary: v0.1 does not implement full multi-instrument score transcription, external video ingestion, OMR, full notation editing, multi-user collaboration, or full export format coverage.

## Implementation Architecture

```mermaid
flowchart TB
    subgraph Frontend["web/ React Workbench"]
        Upload[Audio Upload]
        Waveform[Waveform and Region Selection]
        Editor[Timeline Note Editor]
        AgentPanel[Agent Panel]
        EditPreview[CandidateEdit Preview]
        Revisions[Revision List]
    end

    subgraph Backend["server/ FastAPI"]
        ProjectAPI[Project API]
        UploadAPI[Upload API]
        TaskAPI[Task API]
        DraftAPI[DraftScore API]
        AgentAPI[Agent API]
        EditAPI[Edit API]
        RevisionAPI[Revision API]
        EditEngine[Edit Engine]
        ContextBuilder[Agent Context Builder]
    end

    subgraph Persistence["Persistence"]
        DB[(PostgreSQL)]
        Files[Audio File Storage]
        Redis[(Redis)]
    end

    subgraph Worker["worker/ Celery"]
        Normalize[FFmpeg Normalize]
        Analyze[librosa Analysis]
        AMT[Basic Pitch Adapter]
        Post[Notation Postprocessor]
        DraftBuild[DraftScore Builder]
    end

    subgraph Agent["LLM Layer"]
        Provider[LLM Provider Adapter]
        Schema[Structured Output Validation]
    end

    Upload --> UploadAPI
    UploadAPI --> Files
    UploadAPI --> DB
    UploadAPI --> Redis
    Redis --> Normalize
    Normalize --> Analyze
    Analyze --> AMT
    AMT --> Post
    Post --> DraftBuild
    DraftBuild --> DB
    TaskAPI --> DB
    DraftAPI --> Editor
    Waveform --> AgentPanel
    Editor --> AgentPanel
    AgentPanel --> AgentAPI
    AgentAPI --> ContextBuilder
    ContextBuilder --> Provider
    Provider --> Schema
    Schema --> EditPreview
    EditPreview --> EditAPI
    EditAPI --> EditEngine
    EditEngine --> DB
    EditEngine --> Revisions
```

## Primary Flow

```text
User uploads audio
-> FastAPI stores AudioAsset and creates TranscriptionJob
-> FastAPI dispatches the TranscriptionJob to Celery
-> Celery worker normalizes audio
-> Pipeline generates BeatGrid, NoteEvent, optional ChordEvent
-> Backend stores DraftScore
-> Workbench renders waveform and note timeline
-> User selects local passage
-> Agent context builder extracts local score and audio context
-> LLM adapter returns validated CandidateEdit proposals
-> User confirms one proposal
-> Edit Engine applies it to DraftScore
-> Backend writes Revision
```

## v0.1 Modules

| Module | Directory | Responsibility |
| :--- | :--- | :--- |
| Web Workbench | `web/` | Upload, waveform, note timeline, Agent panel, edit preview |
| API Backend | `server/` | Project, upload, task, draft, Agent, edit, revision APIs |
| Worker | `worker/` | Audio normalization, AMT baseline, postprocessing |
| Persistence | PostgreSQL / file storage | Project, task, DraftScore, audio metadata, CandidateEdit, Revision |
| Queue | Redis / Celery | Long transcription job dispatch |
| Agent Layer | provider adapter | Structured reasoning and CandidateEdit generation |

The worker baseline introduces explicit task dispatch and persisted TranscriptionJob status updates. Full audio normalization and transcription are connected in the pipeline baseline issue.

## v0.1 Data Flow

```mermaid
sequenceDiagram
    participant U as User
    participant W as Web Workbench
    participant B as FastAPI Backend
    participant Q as Redis/Celery
    participant P as Audio Pipeline
    participant D as PostgreSQL
    participant A as Agent Adapter

    U->>W: Upload audio
    W->>B: POST audio
    B->>D: Create Project, AudioAsset, TranscriptionJob
    B->>Q: Enqueue transcription job
    Q->>P: Run worker pipeline
    P->>P: Normalize, analyze, transcribe, postprocess
    P->>D: Store DraftScore
    W->>B: Subscribe / poll task state
    B->>W: draft_ready
    W->>B: Fetch DraftScore
    U->>W: Select local passage and ask Agent
    W->>B: Agent request with SelectionRange
    B->>D: Load DraftScore context
    B->>A: Request structured answer
    A->>B: CandidateEdit proposals
    B->>W: CandidateEdit preview
    U->>W: Confirm edit
    W->>B: Apply CandidateEdit
    B->>D: Update DraftScore and write Revision
```

## v0.1 Runtime States

```text
created
-> uploaded
-> preprocessing
-> transcribing
-> postprocessing
-> draft_ready
-> editing
-> candidate_pending
-> candidate_applied
```

Failure states:

```text
upload_failed
preprocessing_failed
transcription_failed
postprocessing_failed
agent_failed
candidate_conflict
candidate_apply_failed
```
