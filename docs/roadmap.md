# Roadmap

## Development Strategy

AgentClef follows milestone-based development. Each milestone validates one layer of the transcription review workflow and keeps implementation aligned with the product baseline.

```text
v0.1: Minimum transcription review loop
v0.2: Workbench interaction depth
v0.3: Accuracy evaluation and model pipeline
v0.4: Project lifecycle and export
v0.5: Advanced musician workflow features
v1.0: Stable AI Agent transcription review workbench
```

## v0.1 Minimum Transcription Review Loop

Goal: make the first complete product loop usable.

Scope:

- Local audio upload.
- Asynchronous transcription task.
- Single main melody and rhythm draft.
- Optional chord candidates.
- Workbench shell.
- Basic note editing.
- Local selection.
- Agent context and CandidateEdit generation.
- User confirmation.
- Revision log.
- Local quality gates.

## v0.2 Workbench Interaction Depth

Goal: make review faster and more musician-friendly.

Scope:

- Stronger audio and score synchronization.
- Region loop playback.
- Slow playback support.
- Uncertainty list navigation.
- Candidate comparison.
- Improved timeline editing.
- Undo and redo expansion.

## v0.3 Accuracy Evaluation and Model Pipeline

Goal: establish measurable transcription quality.

Scope:

- Fixed evaluation audio fixtures.
- Note onset and pitch evaluation.
- Rhythm and duration review metrics.
- Basic Pitch baseline reporting.
- Model adapter interface.
- Beat and quantization postprocessing improvements.
- Agent suggestion adoption metrics.

## v0.4 Project Lifecycle and Export

Goal: make projects persistent and portable.

Scope:

- Project lifecycle management.
- Audio and draft deletion policy.
- Revision browsing.
- MIDI export.
- MusicXML export baseline.
- Export job tracking.

## v0.5 Advanced Musician Workflow Features

Goal: absorb proven musician workflow patterns.

Scope:

- Chord timeline.
- Transposition support.
- Stem-assisted review research path.
- Instrument-specific transcription modes.
- Existing score alignment research path.

## v1.0 Stable Workbench

Goal: deliver a stable AI Agent assisted transcription review platform.

Scope:

- Documented supported input classes.
- Stable DraftScore schema.
- Reliable transcription review loop.
- Measurable accuracy workflow.
- Confirmed export path.
- Production-ready deployment profile.
