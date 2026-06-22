# Agent Edit Protocol

## Role

The Agent layer assists local transcription review. It explains musical decisions, compares interpretations, and produces structured edit proposals. It does not own score state and does not directly mutate DraftScore.

## Request Context

Each Agent request is grounded in a SelectionRange.

Context payload:

```text
userQuestion
projectId
draftScoreId
draftScoreVersion
selectionRange
localNoteEvents
localChordEvents
beatGridSegment
audioTimeRange
neighboringContext
relatedUncertaintyMarkers
recentRevisions
```

## Response Shape

Agent responses must include structured data:

```text
answer
reasoningSummary
evidence
uncertainty
candidateEdits
requiresUserConfirmation
```

`candidateEdits` must match the CandidateEdit schema and pass backend validation before being shown as actionable edits.

## CandidateEdit Lifecycle

```text
Agent response
-> CandidateEdit validation
-> frontend preview
-> user confirmation
-> backend version check
-> edit engine application
-> Revision creation
-> DraftScore update
```

## Validation Rules

- CandidateEdit must target the current DraftScore version.
- CandidateEdit must reference existing NoteEvent, ChordEvent, or a valid insertion range.
- CandidateEdit must define an edit type supported by v0.1.
- CandidateEdit must include an affected range.
- CandidateEdit must include a user-facing summary.
- CandidateEdit must not apply without explicit confirmation.

## v0.1 Edit Operations

### change_pitch

Changes pitch for an existing NoteEvent.

### change_duration

Changes musical duration and updates the associated audio evidence range when available.

### move_note

Moves a NoteEvent to a new musical start position.

### add_note

Adds a NoteEvent inside a valid selection range.

### delete_note

Deletes an existing NoteEvent.

### change_chord

Changes a ChordEvent label or selects one candidate from a candidate set.

## Example Flow

```text
User selects a high note in measure 24.
User asks: "How long should this high note last?"
Agent receives local NoteEvent, BeatGrid segment, audio time range, and nearby notes.
Agent returns a duration explanation and a change_duration CandidateEdit.
User previews the candidate.
User confirms.
Edit Engine applies the change and records a Revision.
```

## Permission Boundary

- The Agent can propose edits.
- The backend validates edits.
- The user confirms edits.
- The Edit Engine applies edits.
- DraftScore remains the system source of truth.
