# Accuracy Strategy

## Accuracy Definition

AgentClef measures transcription quality across the path from AI draft to confirmed score.

Primary dimensions:

- Draft note pitch and onset quality.
- Draft rhythm and duration usability.
- Beat and measure alignment.
- Chord candidate usefulness.
- User-confirmed final score correctness.
- Review time saved compared with manual transcription.

## v0.1 Internal Targets

v0.1 targets the single main melody and rhythm review workflow.

Internal engineering targets:

- Pitch and onset F1: at least 85%.
- Rhythm and duration usability: at least 75%.
- Final user-reviewed correctness: at least 95%.
- Manual review time reduction: at least 40%.

These targets guide internal evaluation and are not external marketing claims.

## Model Strategy

v0.1 uses a baseline pipeline:

```text
stored audio normalization
-> deterministic timing analysis
-> deterministic AMT adapter boundary
-> BeatGrid mapping
-> Notation postprocessing
-> DraftScore generation
-> UncertaintyMarker generation
```

The model layer is adapter-based. Basic Pitch, librosa-backed analysis, chord models, beat models, and instrument-specific models can be evaluated without changing product logic.

## Evaluation Assets

v0.1 evaluation uses fixed fixtures:

- Short clean melody audio.
- Simple instrument audio.
- Rhythm-focused audio snippets.
- Chord candidate test snippets when enabled.
- Golden DraftScore outputs.

## Metrics

### Automatic Metrics

- Note onset F1.
- Pitch accuracy.
- Offset approximation.
- Beat alignment error.
- Quantization error.
- Chord label match when chord fixtures exist.

### Human Review Metrics

- Number of user corrections.
- Time to final score.
- CandidateEdit adoption rate.
- UncertaintyMarker usefulness.
- Agent answer usefulness.

## Review-Oriented Accuracy

AgentClef optimizes the final score review loop:

```text
model draft
-> uncertainty marker
-> local Agent reasoning
-> candidate edit
-> user confirmation
-> final score
```

The workbench improves accuracy by making likely errors visible, explainable, and quickly correctable.
