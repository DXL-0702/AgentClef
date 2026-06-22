# Product Positioning

## Mission

AgentClef is an AI Agent assisted music transcription review workbench for turning audio into accurate, editable, and exportable musical structure.

The product focuses on the full review path from AI draft to final usable score:

```text
Upload audio
-> Generate editable draft
-> Review the draft in a synchronized workbench
-> Select a local passage
-> Ask the Agent for musical reasoning
-> Preview structured candidate edits
-> Confirm edits
-> Build a finalized score
```

## Product Definition

AgentClef is not a one-click universal transcription converter. Its core value is the review layer after the first AI transcription draft.

The workbench combines:

- Audio playback and timeline context.
- Structured note and beat data.
- Editable draft score state.
- Local passage selection.
- LLM-assisted reasoning.
- Structured CandidateEdit proposals.
- User-confirmed revisions.

## Target Users

v0.1 targets users who need to turn music into a usable draft and are willing to review AI output:

- Music learners reviewing melody and rhythm.
- Creators turning audio fragments into structured musical ideas.
- Users who need help deciding local rhythm, duration, pitch, or chord details.
- Early adopters who value a review workflow over an instant black-box export.

## v0.1 Product Boundary

v0.1 includes:

- Local audio upload.
- Single main melody draft.
- Rhythm and duration draft.
- Optional chord candidates.
- Basic editable note timeline.
- Local Agent discussion.
- Candidate edit confirmation.
- Revision log.

v0.1 excludes:

- Full multi-instrument score transcription.
- External video link ingestion.
- OMR from image or PDF scores.
- Full professional notation editor.
- Multi-user collaboration.
- Full export format matrix.

## Core Differentiation

Most AI transcription tools prioritize the first generated result. AgentClef prioritizes the path from a generated draft to a confirmed score.

The differentiation is expressed in five product mechanics:

- Structured draft score instead of opaque output.
- Uncertainty markers instead of blind review.
- Local passage Agent reasoning instead of generic chat.
- CandidateEdit proposals instead of direct AI mutation.
- Revision records instead of untracked edits.
